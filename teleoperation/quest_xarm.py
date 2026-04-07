"""
Meta quest 3 teleoperate xarm

xarm base: x 向前, y 向左, z 向上
xarm tcp: x 向前, y 向右, z 向下
"""

import numpy as np
import time
import argparse
from scipy.spatial.transform import Rotation as R
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from xarm.wrapper import XArmAPI

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

if project_root not in sys.path:
    sys.path.append(project_root)
from vr.quest_pose import QuestPose

base_position = np.array([0, 0, 0])
base_rotation = np.array([0, 0, 0])
last_pose = None
last_rota = None
arm = None
quest = None
first_timestamp = None
last_timestamp = None

def get_vr():
    print("connecting vr left controller ...")
    quest = QuestPose()
    if not quest.start():
        print("failed to connect vr left controller ...")
        return
    
    wait_start = time.time()
    while not quest.ready():
        time.sleep(0.01)
        if time.time() - wait_start > 5:
            print("connect the vr left controller timeout: cost more than 5s!")
            quest.stop()
            return
    
    test_sequences = []
    print("test vr left controller connect ...")
    for i in range(20):
        pose = quest.get_left()
        if pose is not None:
            test_sequences.append(pose[:3])
            print(f"frame: {i+1:2d}: [{pose[0]:6.3f}, {pose[1]:6.3f}, {pose[2]:6.3f}]")
        else:
            print(f"frame: {i+1:2d}: None")
        time.sleep(0.02)
    
    if len(test_sequences) < 15:
        print("sequences data unstable ...")
        choice = input("continues or stop? (y/n): ")
        if choice.lower() != 'y':
            return

    print("connect successfully!")
    return quest

def get_arm(ip):
    print("connecting arm ...")
    arm = XArmAPI(ip)
    time.sleep(0.5)
    arm.clean_warn()
    arm.clean_error()
    arm.motion_enable(enable=True)
    arm.set_mode(7)
    arm.set_state(0)

    # get initial arm pose
    initial_base_pose = arm.get_position(is_radian=False)[1]
    base_position = np.array(initial_base_pose[:3])
    base_rotation = np.array(initial_base_pose[3:])
    print(f"init arm eef pose: [{base_position[0]}, {base_position[1]}, {base_position[2]}, {base_rotation[0]}, {base_rotation[1]}, {base_rotation[2]}]")
    return arm, base_position, base_rotation

def teleoperation(arm, quest):
    global base_position, base_rotation, last_pose, last_rota, last_timestamp

    try:
        while True:
            pose = quest.get_left()   # vr pose: [x, y, z, qx, qy, qz, qw]
            if pose is not None:
                current_timestamp = time.time()
                init_pose = pose[:3]
                init_rota = pose[3:]

                if last_pose is None:       # if is the first frame, initialize the last_pose and last_rota
                    last_pose = init_pose
                    last_rota = init_rota
                    last_timestamp = time.time()
                    continue
                
                dt = current_timestamp - last_timestamp
                # print(f"freq: {1/dt:4.0f}Hz")

                # relative pose
                # rotation
                delta_position = (init_pose - last_pose) * 1000 # vr m -> xarm mm
                base_position += delta_position

                base_rota = R.from_euler('xyz', base_rotation, degrees=True)
                if not np.allclose(init_rota, last_rota): # if rotation changed, calculate the delta rotation
                    last_rota_rotation = R.from_quat(last_rota)
                    current_quat = R.from_quat(init_rota)
                    delta_rota = current_quat * last_rota_rotation.inv()
                    
                    base_rota = delta_rota * base_rota

                base_rotation = base_rota.as_euler('xyz', degrees=True) # euler angle in degree
      
                last_pose = init_pose
                last_rota = init_rota
                last_timestamp = current_timestamp

                try:
                    arm.set_position(
                        x = base_position[0],
                        y = base_position[1],
                        z = base_position[2],
                        roll = base_rotation[0],
                        pitch = base_rotation[1],
                        yaw = base_rotation[2],
                        speed = 300,
                        wait = False,
                        is_radian = False
                    )

                except Exception as e:
                    print(f"\n teleoperation failed!: {e}")
            else:
                print(f"\n no data! ")
            time.sleep(0.01)  

    except KeyboardInterrupt:
        if quest:
            quest.stop()
        if arm:
            arm.set_mode(0)
            arm.set_state(0)
            time.sleep(0.5)
            arm.disconnect()
        print("\n stop teleoperation ...")

def main(ip):
    global arm, base_position, base_rotation, last_pose, last_rota, quest
    quest = get_vr()
    arm, base_position, base_rotation = get_arm(ip)
    teleoperation(arm, quest)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', type=str, default='192.168.1.244', help='xArm IP')
    args = parser.parse_args()

    main(args.ip)