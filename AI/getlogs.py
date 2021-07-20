import re
import os
import warnings

import numpy as np
import xml.etree.ElementTree as ET
import urllib.request
import gzip
import matplotlib.pyplot as plt

# ======================== Terminology explain ======================

# Match: A set of games on one table until someone flys away or a series of games is finished
# Game: from Init to Agari or Ryukyouku
# Episode: 1 game for 1 player

player_i_hand_start_ind = [0, 63, 69, 75]  # later 3 in oracle_obs
player_i_side_start_ind = [6, 12, 18, 24]
player_i_river_start_ind = [30, 37, 44, 51]

dora_indicator_ind = 58
dora_ind = 59
game_wind_ind = 60
self_wind_ind = 61
wait_tile_ind = 62

aka_tile_ints = [16, 16 + 36, 16 + 36 + 36]
player_obs_width = 63

UNICODE_TILES = """
    🀇 🀈 🀉 🀊 🀋 🀌 🀍 🀎 🀏 
    🀙 🀚 🀛 🀜 🀝 🀞 🀟 🀠 🀡
    🀐 🀑 🀒 🀓 🀔 🀕 🀖 🀗 🀘
    🀀 🀁 🀂 🀃
    🀆 🀅 🀄
""".split()


def decodem(naru_tiles_int, naru_player_id):
    # 54279 : 4s0s chi 6s
    # 35849 : 6s pon
    # 51275 : chu pon
    # ---------------------------------
    binaries = bin(naru_tiles_int)[2:]

    naru_is_aka = False

    if len(binaries) < 16:
        binaries = "0" * (16 - len(binaries)) + binaries

    bit2 = int(binaries[-3], 2)
    bit3 = int(binaries[-4], 2)
    bit4 = int(binaries[-5], 2)

    if bit2:
        naru_type = "Chi"

        bit0_1 = int(binaries[-2:], 2)

        if bit0_1 == 3:  # temporally not used
            source = "kamicha"
        elif bit0_1 == 2:
            source = "opposite"
        elif bit0_1 == 1:
            source = "shimocha"
        elif bit0_1 == 0:
            source = "self"

        bit10_15 = int(binaries[:6], 2)
        bit3_4 = int(binaries[-5:-3], 2)
        bit5_6 = int(binaries[-7:-5], 2)
        bit7_8 = int(binaries[-9:-7], 2)

        which_naru = bit10_15 % 3

        source_player_id = (naru_player_id + bit0_1) % 4

        start_tile_id = int(int(bit10_15 / 3) / 7) * 9 + int(bit10_15 / 3) % 7

        side_tiles_added = [[start_tile_id * 4 + bit3_4, 0], [start_tile_id * 4 + 4 + bit5_6, 0],
                            [start_tile_id * 4 + 8 + bit7_8, 0]]
        # TODO: check aka!
        side_tiles_added[which_naru][1] = 1

        hand_tiles_removed = []
        for kk, ss in enumerate(side_tiles_added):
            if kk != which_naru:
                hand_tiles_removed.append(ss[0])

        if side_tiles_added[which_naru][0] in aka_tile_ints:
            # print("Chi Aka!!!")
            # print(bit3_4, bit5_6, bit7_8)

            naru_is_aka = True

            # print(UNICODE_TILES[start_tile_id], UNICODE_TILES[start_tile_id + 1], UNICODE_TILES[start_tile_id + 2])
            # print(UNICODE_TILES[start_tile_id + which_naru])

        ##### To judge aka, trace previous discarded tile !

    else:
        naru_type = "Pon"

        if bit3:

            bit9_15 = int(binaries[:7], 2)

            which_naru = bit9_15 % 3
            pon_tile_id = int(int(bit9_15 / 3))

            side_tiles_added = [[pon_tile_id * 4, 0], [pon_tile_id * 4 + 1, 0], [pon_tile_id * 4 + 2, 0],
                                [pon_tile_id * 4 + 3, 0]]

            bit5_6 = int(binaries[-7:-5], 2)
            which_not_poned = bit5_6

            del side_tiles_added[which_not_poned]

            side_tiles_added[which_naru][1] = 1

            if side_tiles_added[which_naru][0] in [16, 16 + 36, 16 + 36 + 36]:
                # print("Pon, Aka!!!")
                naru_is_aka = True
                # print(UNICODE_TILES[pon_tile_id], UNICODE_TILES[pon_tile_id], UNICODE_TILES[pon_tile_id])

            hand_tiles_removed = []
            for kk, ss in enumerate(side_tiles_added):
                if kk != which_naru:
                    hand_tiles_removed.append(ss[0])

        else:  # An-Kan, Min-Kan, Add-Kan
            naru_type = "Kan"

            bit5_6 = int(binaries[-7:-5], 2)
            which_kan = bit5_6

            if bit4:
                #  print("Add-Kan")  # TODO: Add-Kan Only change 1 tile
                bit9_15 = int(binaries[:7], 2)

                kan_tile_id = int(bit9_15 / 3)

                side_tiles_added = [[kan_tile_id * 4 + which_kan, 1]]

                if (kan_tile_id * 4 + which_kan) in aka_tile_ints:
                    naru_is_aka = True

                hand_tiles_removed = [kan_tile_id * 4 + which_kan]

            else:  # An-Kan or Min-Kan

                which_naru = naru_tiles_int % 4

                bit8_15 = int(binaries[:8], 2)

                kan_tile = bit8_15
                kan_tile_id = int(kan_tile / 4)

                which_kan = kan_tile % 4

                side_tiles_added = [[kan_tile_id * 4, 0], [kan_tile_id * 4 + 1, 0], [kan_tile_id * 4 + 2, 0],
                                    [kan_tile_id * 4 + 3, 0]]
                if which_naru == 0:
                    # print("An-Kan")
                    hand_tiles_removed = []
                    for kk, ss in enumerate(side_tiles_added):
                        hand_tiles_removed.append(ss[0])
                else:
                    # print("Min-Kan")
                    side_tiles_added[which_kan][1] = 1

                    hand_tiles_removed = []
                    for kk, ss in enumerate(side_tiles_added):
                        if kk != which_kan:
                            hand_tiles_removed.append(ss[0])

    return side_tiles_added, hand_tiles_removed, naru_is_aka, naru_type


def dora2indicator(dora_id):
    if dora_id == 0:  # 1m
        indicator_id = 8  # 9m
    elif dora_id == 9:  # 1p
        indicator_id = 17  # 9p
    elif dora_id == 18:  # 1s
        indicator_id = 26  # 9s
    elif dora_id == 27:  # East
        indicator_id = 30  # North
    elif dora_id == 31:  # Hake
        indicator_id = 33  # Chu
    else:
        indicator_id = dora_id - 1
    return indicator_id


def generate_obs(hand_tiles, river_tiles, side_tiles, dora_tiles, game_wind, self_wind):
    all_obs = np.zeros([4, 34, 63 + 18], dtype=np.uint8)

    global player_i_hand_start_ind
    global player_i_side_start_ind
    global player_i_river_start_ind

    global dora_indicator_ind
    global dora_ind
    global game_wind_ind
    global self_wind_ind
    global wait_tile_ind

    global aka_tile_ints

    # ----------------- Side Tiles Process ------------------
    for player_id, player_side_tiles in enumerate(side_tiles):
        side_tile_num = np.zeros(34, dtype=np.uint8)
        for side_tile in player_side_tiles:
            side_tile_id = int(side_tile[0] / 4)
            side_tile_num[side_tile_id] += 1

            if side_tile[0] in aka_tile_ints:
                # Red dora
                all_obs[player_id, side_tile_id, player_i_side_start_ind[player_id] + 5] = 1

            all_obs[player_id, side_tile_id, player_i_side_start_ind[player_id] + 4] = side_tile[1]

        for t_id in range(34):
            for k in range(4):
                if side_tile_num[t_id] > k:
                    all_obs[player_id, t_id, player_i_side_start_ind[player_id] + k] = 1

    # ----------------- River Tiles Procces ------------------
    for player_id, player_river_tiles in enumerate(river_tiles):  # 副露也算在牌河里, also include Riichi info
        river_tile_num = np.zeros(34, dtype=np.uint8)
        for river_tile in player_river_tiles:
            river_tile_id = int(river_tile[0] / 4)

            all_obs[player_id, river_tile_id, player_i_hand_start_ind[player_id] + 4] = 1

            river_tile_num[river_tile_id] += 1

            if river_tile[0] in aka_tile_ints:  # Red dora
                all_obs[player_id, river_tile_id, player_i_river_start_ind[player_id] + 5] = 1

            # te-kiri (from hand)
            all_obs[player_id, river_tile_id, player_i_river_start_ind[player_id] + 4] += river_tile[1]

            # is riichi-announcement tile
            all_obs[player_id, river_tile_id, player_i_river_start_ind[player_id] + 6] += river_tile[2]

        for t_id in range(34):
            for k in range(4):
                if river_tile_num[t_id] > k:
                    all_obs[player_id, t_id, player_i_river_start_ind[player_id] + k] = 1

    # ----------------- Hand Tiles Process ------------------
    for player_id, player_hand_tiles in enumerate(hand_tiles):
        hand_tile_num = np.zeros(34, dtype=np.uint8)
        for hand_tile in player_hand_tiles:
            hand_tile_id = int(hand_tile / 4)
            hand_tile_num[hand_tile_id] += 1

            if hand_tile in aka_tile_ints:
                # Aka dora
                all_obs[player_id, hand_tile_id, player_i_hand_start_ind[player_id] + 5] = 1

            # how many times this tile has been discarded before by this player
            all_obs[player_id, hand_tile_id, player_i_hand_start_ind[player_id] + 4] = (np.sum(
                all_obs[player_id, hand_tile_id,
                player_i_river_start_ind[player_id]:player_i_river_start_ind[player_id] + 4])) > 0

        for t_id in range(34):
            for k in range(4):
                if hand_tile_num[t_id] > k:
                    all_obs[player_id, t_id, player_i_hand_start_ind[player_id] + k] = 1

    # ----------------- Dora Process ------------------
    for dora_tile in dora_tiles:
        dora_hai_id = int(dora_tile / 4)
        all_obs[:, dora_hai_id, dora_ind] += 1
        all_obs[:, dora2indicator(dora_hai_id), dora_indicator_ind] += 1

    # ----------------- Public Game State ----------------
    all_obs[:, :, game_wind_ind] = game_wind  # Case 1 to 4 in dim 0
    all_obs[:, :, self_wind_ind] = self_wind

    # players_obs = all_obs[:, :, :63]
    # oracles_obs = all_obs[:, :, 63:]

    return all_obs


paipu_urls = []

path = "../2020_paipu"
files = os.listdir(path)  # 得到文件夹下的所有文件名称

filenames = []

for file in files:  # 遍历文件夹
    if not os.path.isdir(file) and file[-4:] == "html":  # 判断是否是文件夹，不是文件夹才打开
        filenames.append(path + "/" + file)  # 打开文件
#         print(file)

for filename in filenames:

    f = open(filename, 'r', encoding='UTF-8')

    scc = f.read()
    # print(scc)

    f.close()

    replay_urls = re.findall('href="(.+?)">', scc)

    log_urls = []

    for tmp in replay_urls:
        log_url_split = tmp.split("?log=")
        log_urls.append(log_url_split[0] + "log?" + log_url_split[1])

    paipu_urls = paipu_urls + log_urls

# -------------- Hyper-parameters ------------------

max_ten_diff = 250  # 最大点数限制，排除点数差距过大时的非正常打法
min_dan = 16  # 最低段位限制，可以排除三麻的局（三麻的缺省player的dan=0）

max_aval_action_num = 16
max_all_steps = 100000
max_steps = 200

player_obs_total = np.zeros([max_all_steps, 1, 34, 63], dtype=np.uint8)
oracle_obs_total = np.zeros([max_all_steps, 1, 34, 18], dtype=np.uint8)
player_actions_total = np.zeros([max_all_steps, max_aval_action_num, 1, 34, 63], dtype=np.uint8)
oracle_actions_total = np.zeros([max_all_steps, max_aval_action_num, 1, 34, 18], dtype=np.uint8)
int_actions_total = np.zeros([max_all_steps], dtype=np.uint8)
valid_init_actions_total = np.zeros([max_all_steps], dtype=np.uint8)
aval_actions_num_total = np.zeros([max_all_steps], dtype=np.uint8)

done_total = np.zeros([max_all_steps], dtype=np.float32)
reward_total = np.zeros([max_all_steps], dtype=np.float32)

hosts = ["e3.mjv.jp",
         "e4.mjv.jp",
         "e5.mjv.jp",
         "k0.mjv.jp",
         "e.mjv.jp"]

num_games = 0
game_has_init = False

sum_scores = np.zeros(4, dtype=np.float64)
oya_scores = np.zeros(1, dtype=np.float64)

machi_hai_freq = np.zeros(136, dtype=np.float64)
# ----------------- start ---------------------

for url in paipu_urls:
    for host in hosts:

        try:
            HEADER = {
                'Host': host,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }

            req = urllib.request.Request(url=url, headers=HEADER)
            opener = urllib.request.build_opener()
            response = opener.open(req)
            #         print(response.read())
            paipu = gzip.decompress(response.read()).decode('utf-8')
            #         print(paipu)
            break
        except:
            pass

    root = ET.fromstring(paipu)

    # =================== 开始解析牌谱 =======================

    print("=================== 开始解析牌谱 =======================")

    record_this_game = True

    for child_no, child in enumerate(root):
        # Initial information, discard
        if child.tag == "SHUFFLE":
            #         print(child.attrib)
            pass

        elif child.tag == "GO":  # 牌桌规则和等级等信息.
            #         print(child.attrib)
            type_num = int(child.get("type"))
            tmp = str(bin(type_num))

            game_info = dict()
            game_info["is_pvp"] = int(tmp[-1])
            if not game_info["is_pvp"]:
                break

            game_info["no_aka"] = int(tmp[-2])
            if game_info["no_aka"]:
                break

            game_info["no_kuutan"] = int(tmp[-3])
            if game_info["no_kuutan"]:
                break

            game_info["is_hansou"] = int(tmp[-4])
            # no requirement

            game_info["is_3ma"] = int(tmp[-5])
            if game_info["is_3ma"]:
                break

            game_info["is_pro"] = int(tmp[-6])
            # no requirement

            game_info["is_fast"] = int(tmp[-7])
            if game_info["is_fast"]:
                break

            game_info["is_joukyu"] = int(tmp[-8])

            # for key in game_info:
            #     print(key, game_info[key])

            # 0x01	如果是PVP对战则为1
            # 0x02	如果没有赤宝牌则为1
            # 0x04	如果无食断则为1
            # 0x08	如果是半庄则为1
            # 0x10	如果是三人麻将则为1
            # 0x20	如果是特上卓或凤凰卓则为1
            # 0x40	如果是速卓则为1
            # 0x80	如果是上级卓则为1

        elif child.tag == "TAIKYOKU":
            pass

        elif child.tag == "UN":
            #         print(child.attrib)
            if "dan" in child.attrib:
                dans_str = child.get("dan").split(',')
                dans = [int(tmp) for tmp in dans_str]

                if min(dans) < min_dan:
                    break  # not record this whole game

        elif child.tag == "INIT":
            record_this_game = True

            scores_change_this_game = np.zeros([4])

            players_episode_all_obs = [[], [], [], []]

            # print(child.attrib)

            # print("------------------------------------")
            # player_obs = np.zeros([4, max_steps, 1, 34, 60], dtype=np.uint8)
            # oracle_obs = np.zeros([4, max_steps, 1, 34, 15], dtype=np.uint8)
            # player_actions = np.zeros([4, max_steps, max_aval_action_num, 1, 34, 60], dtype=np.uint8)
            # oracle_actions = np.zeros([4, max_steps, max_aval_action_num, 1, 34, 15], dtype=np.uint8)
            # aval_actions_num = np.zeros([4, max_steps], dtype=np.uint8)

            # scores_number
            scores_str = child.get("ten").split(',')
            scores = [int(tmp) for tmp in scores_str]

            #             if max(scores) - min(scores) > max_ten_diff:
            #                 record_this_game = False
            #             else:
            #                 record_this_game = True
            #         print(scores)

            # Oya number
            oya_id = int(child.get("oya"))

            game_wind_obs = np.zeros(34)  # index: -4
            game_wind_obs[27] = 1

            self_wind_obs = np.zeros([4, 34])  # index: -3
            self_wind_obs[0, 27 + (4 - oya_id) % 4] = 1
            self_wind_obs[1, 27 + (5 - oya_id) % 4] = 1
            self_wind_obs[2, 27 + (6 - oya_id) % 4] = 1
            self_wind_obs[3, 27 + (7 - oya_id) % 4] = 1

            dora_tiles = [int(child.get("seed").split(",")[-1])]

            hand_tiles = []
            for player_id in range(4):
                tiles_str = child.get("hai{}".format(player_id)).split(",")
                hand_tiles_player = [int(tmp) for tmp in tiles_str]
                hand_tiles.append(hand_tiles_player)

            river_tiles = [[], [], [], []]  # each has 3 elements: tile_no, is_from_hand and riichi_announce_tile
            side_tiles = [[], [], [], []]  # each has 2 elements: tile_no and is_naru_tile

            # ----------------------- Generate initial player and oracle observaTION  ----------------

            curr_all_obs = generate_obs(hand_tiles, river_tiles, side_tiles, dora_tiles, game_wind_obs, self_wind_obs)

            game_has_init = True

        # ------------------------- Actions ---------------------------

        elif record_this_game:

            if not game_has_init:
                record_this_game = False
                for cc in range(min(child_no + 4, len(root))):
                    print(root[cc].tag, root[cc].attrib)
                warnings.warn("============= Game has not been correctly initialized, skipped ================")
                continue

            if child.tag == "DORA":
                # --------------- update game states -------------
                dora_tiles.append(int(child.get("hai")))

                # --------------- Update observations --------------
                new_dora_hai_id = int(int(child.get("hai")) / 4)
                curr_all_obs[:, new_dora_hai_id, dora_ind] += 1
                new_dora_indicator_id = dora2indicator(new_dora_hai_id)
                curr_all_obs[:, new_dora_indicator_id, dora_indicator_ind] += 1

                # TODO: update in Kan

            elif child.tag == "REACH":

                # ---------------- Record statistics ------------
                if int(child.get("step")) == 2:
                    player_id = int(child.get("who"))
                    sum_scores[player_id] -= 10
                    scores_change_this_game[player_id] -= 10
                    if oya_id == player_id:
                        oya_scores -= 10

                    # --------------- update game states -------------
                    # Not updating states here, but during dicarding tile stage

                    # --------------- Update observations --------------
                    # Not updating states here, but during dicarding tile stage

                # ---------- TODO: compute next aval obs ----------
                if int(child.get("step")) == 1:
                    pass

            elif child.tag[0] in ["T", "U", "V", "W"] and child.attrib == {}:  # 摸牌
                if child.tag[0] == "T":
                    player_id = 0
                elif child.tag[0] == "U":
                    player_id = 1
                elif child.tag[0] == "V":
                    player_id = 2
                elif child.tag[0] == "W":
                    player_id = 3
                else:
                    raise ValueError

                # --------------- update game states -------------
                obtained_tile = int(child.tag[1:])
                obtained_tile_id = int(obtained_tile / 4)

                hand_tiles[player_id].append(int(child.tag[1:]))

                # --------------- update game  observations -------------
                if obtained_tile in aka_tile_ints:
                    curr_all_obs[player_id, obtained_tile_id, player_i_hand_start_ind[player_id] + 5] = 1

                hand_num_tile = np.sum(curr_all_obs[player_id, obtained_tile_id,
                                       player_i_hand_start_ind[player_id]:player_i_hand_start_ind[player_id] + 4])
                if hand_num_tile < 0 or hand_num_tile > 3:
                    raise ValueError
                curr_all_obs[player_id, obtained_tile_id, player_i_hand_start_ind[player_id] + hand_num_tile] = 1

                # TODO: state-transition record?

            elif child.tag[0] in ["D", "E", "F", "G"] and child.attrib == {}:  # 打牌

                if child.tag[0] == "D":
                    player_id = 0
                elif child.tag[0] == "E":
                    player_id = 1
                elif child.tag[0] == "F":
                    player_id = 2
                elif child.tag[0] == "G":
                    player_id = 3
                else:
                    raise ValueError

                # --------------- update game states  -------------
                discard_tile = int(child.tag[1:])
                discard_tile_id = int(discard_tile / 4)

                if root[child_no + 1].tag == "REACH" and root[child_no + 1].get("step") == '2':
                    if not (root[child_no - 1].tag == "REACH" and root[child_no - 1].get("step") == '1'):
                        raise ValueError("Some problems!!!")

                if root[child_no - 1].tag == "REACH" and root[child_no - 1].get("step") == '1':  # TODO: is this OK?
                    is_riichi_announcement_tile = 1
                else:
                    is_riichi_announcement_tile = 0

                if child.tag[1:] != root[child_no - 1 - is_riichi_announcement_tile].tag[1:]:  # from hand (te kiri)
                    is_from_hand = 1
                else:
                    is_from_hand = 0

                river_tiles[player_id].append([discard_tile, is_from_hand, is_riichi_announcement_tile])
                hand_tiles[player_id].remove(discard_tile)
                # --------------- update observations -------------

                if discard_tile in aka_tile_ints:
                    curr_all_obs[player_id, discard_tile_id, player_i_hand_start_ind[player_id] + 5] = 0
                    curr_all_obs[player_id, discard_tile_id, player_i_river_start_ind[player_id] + 5] = 1

                curr_all_obs[player_id, discard_tile_id, player_i_river_start_ind[player_id] + 4] += is_from_hand
                curr_all_obs[player_id, discard_tile_id, player_i_river_start_ind[player_id] + 6] = is_riichi_announcement_tile

                river_num_tile = np.sum(curr_all_obs[player_id, discard_tile_id,
                                        player_i_river_start_ind[player_id]:player_i_river_start_ind[player_id] + 4])

                if river_num_tile < 0 or river_num_tile > 3:
                    raise ValueError
                curr_all_obs[player_id, discard_tile_id, player_i_river_start_ind[player_id] + river_num_tile] = 1

                # if discard, change hand tile obs:
                curr_all_obs[player_id, discard_tile_id, player_i_hand_start_ind[player_id] + 4] = 1

                hand_num_tile = np.sum(curr_all_obs[player_id, discard_tile_id, player_i_hand_start_ind[player_id]:player_i_hand_start_ind[player_id] + 4])
                if hand_num_tile < 1 or hand_num_tile > 4:
                    raise ValueError

                curr_all_obs[player_id, discard_tile_id, player_i_hand_start_ind[player_id] + hand_num_tile - 1] = 0

            elif child.tag == "N":  # 鸣牌
                naru_player_id = int(child.get("who"))
                player_id = naru_player_id
                naru_tiles_int = int(child.get("m"))

                # print("==========  Naru =================")
                side_tiles_added_by_naru, hand_tiles_removed_by_naru, naru_is_aka, naru_type = decodem(
                    naru_tiles_int, naru_player_id)

                # print("This game has ", naru_type)

                if int(root[child_no - 1].tag == "REACH"):
                    trace_back_steps = 2
                else:
                    trace_back_steps = 1

                # --------------- update game states  -------------
                side_tiles[player_id] = side_tiles[player_id] + side_tiles_added_by_naru

                for hh in hand_tiles_removed_by_naru:
                    hand_tiles[player_id].remove(hh)
                # TODO: Kan might have error

                # --------------- update observations -------------

                for side_tile in side_tiles_added_by_naru:
                    side_tile_id = int(side_tile[0] / 4)
                    side_num_tile = np.sum(curr_all_obs[player_id, side_tile_id,
                                           player_i_side_start_ind[player_id]:player_i_side_start_ind[player_id] + 4])
                    if side_num_tile < 0 or side_num_tile > 3:
                        raise ValueError

                    curr_all_obs[player_id, side_tile_id, player_i_side_start_ind[player_id] + side_num_tile] = 1
                    curr_all_obs[player_id, side_tile_id, player_i_side_start_ind[player_id] + 4] = side_tile[1]

                    if side_tile[0] in aka_tile_ints:
                        curr_all_obs[player_id, side_tile_id, player_i_side_start_ind[player_id] + 5] = 1

                for hand_tile in hand_tiles_removed_by_naru:
                    hand_tile_id = int(hand_tile / 4)
                    hand_num_tile = np.sum(curr_all_obs[player_id, hand_tile_id,
                                           player_i_hand_start_ind[player_id]:player_i_hand_start_ind[player_id] + 4])

                    if hand_num_tile < 1 or hand_num_tile > 4:
                        raise ValueError

                    curr_all_obs[player_id, hand_tile_id, player_i_hand_start_ind[player_id] + hand_num_tile - 1] = 0

                    if naru_type == "Kan" or (hand_tile in aka_tile_ints):
                        curr_all_obs[player_id, hand_tile_id, player_i_hand_start_ind[player_id] + 5] = 0

                # ------------ check --------
                # if int(root[child_no - trace_back_steps].tag[1:]) in aka_tile_ints:
                # if naru_is_aka:
                #     print(root[child_no - trace_back_steps].tag)
                #     print("narued tile is", UNICODE_TILES[int(int(root[child_no - trace_back_steps].tag[1:]) / 4)])
                #     print("This naru contains Aka !!")
                #     print("==========  Naru =================")
                # add into side tiles

                # remove from hand tiles

            elif child.tag == "BYE":  # 掉线
                record_this_game = False
                break

            elif child.tag == "RYUUKYOKU" or child.tag == "AGARI":

                # ------------------- Statistics -------------------------

                # scores_change_str = child.get("sc").split(",")
                # scores_change = [int(tmp) for tmp in scores_change_str]
                # rewards = scores_change[1::2]
                #
                # oya_scores += rewards[oya_id]
                #
                # if child.tag == "AGARI":
                #     # double-ron
                #     if len(child.get("who")) > 1:
                #         for c in root:
                #             print(c.tag, c.attrib)
                #         raise ValueError("from who is not single player!!!")
                #
                #     machi_hai_str = child.get("machi").split(",")
                #     machi_hai = np.array([int(tmp) for tmp in machi_hai_str]).astype(np.int)
                #
                #     machi_hai_freq[machi_hai] += 1
                #
                # for player_id in range(4):
                #     sum_scores[player_id] += rewards[player_id]
                #     scores_change_this_game[player_id] += rewards[player_id]
                #
                # if "owari" in child.attrib:
                #     owari_scores_change_str = child.get("sc").split(",")
                #     owari_scores_change = [int(tmp) for tmp in owari_scores_change_str]
                #     if np.sum(owari_scores_change) > 1000:
                #         print(owari_scores_change)

                # ---------------------- Check observation generation ---------------

                if child.tag == "AGARI":

                    agari_player_id = int(child.get("who"))
                    # ---------------- update observations ---------------------
                    agari_tile = int(child.get("machi"))
                    agari_tile_id = int(agari_tile / 4)

                    if child.get("who") != child.get("fromWho"):  # not tsumo
                        hand_num_tile = np.sum(curr_all_obs[agari_player_id, agari_tile_id,
                                                            player_i_hand_start_ind[agari_player_id]:player_i_hand_start_ind[agari_player_id] + 4])
                        curr_all_obs[agari_player_id, agari_tile_id, player_i_hand_start_ind[agari_player_id] + hand_num_tile] = 1

                    if agari_tile in aka_tile_ints:
                        curr_all_obs[agari_player_id, agari_tile_id, player_i_hand_start_ind[agari_player_id] + 5] = 1

                    # hand_tiles[agari_player_id].append(agari_tile)
                    # can choose to agari or not
                    # TODO: consider tsumo

                    # ---------------- update game states ----------------------

                    hand_tiles[agari_player_id] = [int(hai) for hai in child.get("hai").split(",")]

                    # if hasattr(child, "m"):
                    #     side_tiles_agari_str = child.get("m").split(",")
                    #     side_tiles[agari_player_id] = []
                    #     for ss in side_tiles_agari_str:
                    #         side_tiles_added, _, _, _ = decodem(int(ss), agari_player_id)
                    #         side_tiles[agari_player_id].append(side_tiles_added)

                    # TODO: record state transition

                # Multiple player Agari:
                if child_no + 1 < len(root) and (root[child_no + 1].tag == "AGARI" or root[child_no + 1].tag == "BYE"):
                    continue

                curr_all_obs_final = generate_obs(
                    hand_tiles, river_tiles, side_tiles, dora_tiles, game_wind_obs, self_wind_obs)

                if root[child_no - 2].tag == "REACH" and root[child_no - 2].get("step") == '1':  # Riichi Tile Ron
                    riichi_tile = int(root[child_no - 1].tag[1:])
                    riichi_player_id = int(root[child_no - 2].get("who"))
                    riichi_tile_id = int(riichi_tile / 4)
                    curr_all_obs[riichi_player_id, riichi_tile_id, player_i_river_start_ind[riichi_player_id] + 6] = 0

                    curr_all_obs_final[riichi_player_id, riichi_tile_id, player_i_river_start_ind[riichi_player_id] + 6] = 0

                if np.all(curr_all_obs_final == curr_all_obs):
                    print("state observation no problem!")

                else:
                    print("------------------------------------------------------")
                    for pid in range(4):
                        print("player {} :".format(pid))
                        for i in range((curr_all_obs_final == curr_all_obs).shape[1]):
                            for j in range((curr_all_obs_final == curr_all_obs).shape[2]):
                                if not (curr_all_obs_final == curr_all_obs)[pid, i, j]:
                                    print("Inconsistency: Tile ID {}, feature index {}".format(i, j))
                                    print("Processed One is {}, Finally Generated One is {}".format(
                                        curr_all_obs[pid, i, j], curr_all_obs_final[pid, i, j]))

                #                     for pid in range(4):
                #                         plt.subplot(1, 2, 1)
                #                         plt.pcolor(curr_all_obs[pid])

                #                         plt.subplot(1, 2, 2)
                #                         plt.pcolor(curr_all_obs_final[pid])
                #                         plt.show()



                num_games += 1
                done = True

                # if num_games == 10:
                #     stop

                if num_games % 100 == 0:

                    print(num_games)
                    print("avg_scores:", sum_scores / num_games)

                    # print("avg_oya_scores:", oya_scores / num_games)
                    # print("machi hai frequency:", machi_hai_freq / num_games)

                if child_no + 1 < len(root) and root[child_no + 1].tag == "AGARI":
                    game_has_init = True  # many players agari
                else:
                    game_has_init = False

                # --------------------- Add data to the total buffer ------------------
                if record_this_game:
                    pass  # TODO

            else:
                print(child.tag, child.attrib)

                raise ValueError("Unexpected Element!")

