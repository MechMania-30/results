import os
from os import path
import shutil

from tqdm import tqdm

# Converts preraw dirs into singular raw dir with duplicates removed
# Requires games output from process.py to determine which games need to stay

# Uses tqdm (can remove if needed)


PRERAW_DIR = "./preraw"
GAMES_DIR = "./games"
RAW_DIR = "./raw"

game_ids = set(os.listdir(GAMES_DIR))

try:
    shutil.rmtree(RAW_DIR)
except:
    pass
os.makedirs(RAW_DIR, exist_ok=True)

game_paths = dict()

for dir in os.listdir(PRERAW_DIR):
    dir_path = path.join(PRERAW_DIR, dir)
    for game_dir in os.listdir(dir_path):
        if game_dir in game_ids:
            game_paths[game_dir] = path.join(dir_path, game_dir)

for game_id, game_path in tqdm(game_paths.items()):
    dest = path.join(RAW_DIR, game_id)
    shutil.copytree(game_path, dest)
