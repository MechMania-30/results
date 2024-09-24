import os
import shutil

# Given a dir, take all dirs in subdirs and move them up to parent dir

parent_dir = './'

for root, dirs, files in os.walk(parent_dir):
    for dir_name in dirs:
        full_path = os.path.join(root, dir_name)
        if root != parent_dir:
            shutil.move(full_path, parent_dir)
