"""
Quest 位姿读取器 - 持续读取左手柄机器人坐标系位姿
输出格式: [x, y, z, qx, qy, qz, qw]
"""

import json
import socket
import threading
import numpy as np
from scipy.spatial.transform import Rotation
import time

class QuestPose:
    def __init__(self, host="localhost", port=7777):
        self.host = host
        self.port = port
        self.sock = None
        self.buffer = ""
        self.running = False
        self.thread = None
        self.left = None
        self.lock = threading.Lock()
        self.Q = np.array([[0,  0, 1],   # x axis -> -y axis
                           [-1, 0, 0],   # y axis -> z axis
                           [0,  1, 0]])  # z axis -> y axis
    
    def _to_robot(self, pose):
        # transfer left coordinate to right coordinate
        p = np.array(pose)
        p[:3] = self.Q @ p[:3]
        R = Rotation.from_quat(p[3:]).as_matrix()
        R = self.Q @ R @ self.Q.T
        return np.concatenate([p[:3], Rotation.from_matrix(R).as_quat()])
    
    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.1)
            self.sock.connect((self.host, self.port))
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            return True
        except:
            return False
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.sock:
            self.sock.close()
    
    def _run(self):
        while self.running:
            try:
                data = self.sock.recv(4096).decode()
                self.buffer += data
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if line.strip():
                        self._parse(line)
            except:
                continue
    
    def _parse(self, line):
        try:
            data = json.loads(line)
            if 'left_wrist' in data:
                l = data['left_wrist']
                pose = [
                    l['position']['x'], l['position']['y'], l['position']['z'],
                    l['rotation']['x'], l['rotation']['y'], l['rotation']['z'], l['rotation']['w'] 
                ]
                # print(f"pose: {pose}")
                with self.lock:
                    self.left = self._to_robot(pose) # change left hand coordinate to right hand coordinate

        except:
            pass
    
    def get_left(self):
        with self.lock:
            return self.left.copy() if self.left is not None else None
    
    def ready(self):
        with self.lock:
            return self.left is not None


if __name__ == "__main__":
    quest = QuestPose() # x, y, z, qx, qy, qz, qw
    if not quest.start():
        print("connection failed")
        exit()
    
    while not quest.ready():
        time.sleep(0.1)
    
    try:
        while True:
            pose = quest.get_left()
            if pose is not None:
                print(f"vr left controller pose: [x:{pose[0]:6.3f}, y:{pose[1]:6.3f}, z:{pose[2]:6.3f}, "
                      f"qx:{pose[3]:6.3f}, qy:{pose[4]:6.3f}, qz:{pose[5]:6.3f}, qw:{pose[6]:6.3f}]")
            time.sleep(0.1) 
    except KeyboardInterrupt:
        print("\n退出")
    finally:
        quest.stop()