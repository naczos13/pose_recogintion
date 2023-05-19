import cv2
import mediapipe as mp
import numpy as np
import random
import math
from threading import Thread
import time
import sys


class VideoStreamWidget(object):
    def __init__(self, capure_input_from_camera=True):
        ### Constans
        ## Tune mediapipe detection and tracking
        self.POSE_DETECTOR = mp.solutions.pose.Pose(
            min_detection_confidence=0.5, min_tracking_confidence=0.5
        )
        self.PROGRAM_NAME = "Simon Says"
        self.FIRST_FRAME_PATH = "static/first_frame.jpg"
        self.ACTION_RADIUS = 20
        self.MP_POSE = mp.solutions.pose.PoseLandmark
        self.PATH_TO_HIGH_SCORE = "static/high_score.txt"
        self.TIME_LIMIT_PER_ROUND = 10
        
        if capure_input_from_camera:
            # Start the thread to read frames from the video stream
            self._thread = Thread(target=self.update, args=())
            self._thread.daemon = True
            self._thread.start()

        self._action_hand, self._base_part = self.regenerate_simon_instruction()
        self._highest_score = self.read_highest_score_from_file(self.PATH_TO_HIGH_SCORE)
        self._current_score = 0
        self._capture = None # Camera capture
        self._landmarks = None # Body parts position landmarks
        self._raw_right_menu = cv2.imread('static/menu_bar.jpg')
        self._games_runs = False    

    def update(self):
        self._capture = cv2.VideoCapture(0)
        # Read the next frame from the stream in a different thread
        while True:
            if self._capture.isOpened():
                (_, self._raw_frame) = self._capture.read()
                self._pose_detection_results = self.find_human_pose_in_image(raw_camera_frame=self._raw_frame)
            time.sleep(0.01)

    def show_frame(self):
        # input is raw_frame
        try:
            frame = self._raw_frame.copy()
            right_menu = self._raw_right_menu.copy()
        except AttributeError:
            pass
        # check the landmarks
        try:
            if self._games_runs:
                self._landmarks = self._pose_detection_results.pose_landmarks.landmark
                frame = self.draw_action_hand(camera_frame=frame, action_hand=self._action_hand, landmarks=self._landmarks)
                frame = self.draw_base_body_part(camera_frame=frame, target_body_part=self._base_part, landmarks=self._landmarks)
                elapsed = self.TIME_LIMIT_PER_ROUND - round(time.time() - self._time_start)
                if elapsed < 0:
                    self._games_runs = False
                right_menu = self.show_timer(right_bar=right_menu, elapsed=elapsed)
                if self.done_what_simon_said(active_hand=self._action_hand,
                                            target_body_part=self._base_part,
                                            landmarks=self._landmarks,
                                            camera_frame=frame):
                    self._action_hand, self._base_part = self.regenerate_simon_instruction()
                    self._current_score += 1
                    if self._current_score > self._highest_score:
                        self._highest_score = self._current_score
        except (KeyError, AttributeError):
            pass

        right_menu = self.draw_scores(right_bar=right_menu, max_score=self._highest_score, current_score=self._current_score)
        right_menu = self.draw_instruction(right_bar=right_menu)
        
        
        # Display frames in main program
        canvas = self.concate_camera_frame_with_menu(camera_frame=frame, right_bar=right_menu)
        cv2.imshow(self.PROGRAM_NAME, canvas)
        key = cv2.waitKey(1)
        if key == ord("q"):
            self.exit_program()
        if key == ord("s") or key == ord("r"):
            self._games_runs = True
            self._time_start = time.time()
            self._current_score = 0
    
    def show_timer(self, right_bar, elapsed):
        font = cv2.FONT_HERSHEY_COMPLEX_SMALL
        pos_x = 10  
        pos_y = 300
        color = (0, 0, 255) # red
        str_to_display = f"Remained {elapsed}s"
        right_bar = cv2.putText(right_bar, str_to_display, (pos_x, pos_y), font, 
                   1, color, 1, cv2.LINE_AA)
        return right_bar
        
            
    def read_highest_score_from_file(self, path):
        try:
            with open(path, 'r') as file:
                high_score = file.readline()
        except FileNotFoundError:
            return 0
            
        try:
            high_score = int(high_score)
            return high_score
        except ValueError:
            return 0
    
    def draw_instruction(self, right_bar):
        font = cv2.FONT_HERSHEY_COMPLEX_SMALL
        pos_x = 10  
        pos_y = 150
        color = (0, 0, 0) # black
        
        right_bar = cv2.putText(right_bar, "To score a point", (pos_x, pos_y), font, 
                   1, color, 1, cv2.LINE_AA)
        
        pos_y = 170
        right_bar = cv2.putText(right_bar, "connect", (pos_x, pos_y), font, 
                   1, color, 1, cv2.LINE_AA)
        
        right_bar = cv2.circle(right_bar, (pos_x + (self.ACTION_RADIUS), pos_y + (2*self.ACTION_RADIUS)), self.ACTION_RADIUS, (0, 255, 0), -1)
        
        right_bar = cv2.putText(right_bar, "to", (pos_x + (2 * self.ACTION_RADIUS + 10), pos_y + (2*self.ACTION_RADIUS)), font, 
                   1, color, 1, cv2.LINE_AA)
        
        right_bar = cv2.circle(right_bar, (pos_x + (5*self.ACTION_RADIUS), pos_y + (2*self.ACTION_RADIUS)), self.ACTION_RADIUS, (255, 0, 0), -1)
        
        return right_bar
      
    def draw_scores(self, right_bar, max_score, current_score):
        font = cv2.FONT_HERSHEY_COMPLEX_SMALL
        pos_x = 10  
        pos_y = 50
        color = (255, 0, 0) # blue
        
        str_current_score = f"Current Score: {current_score}"
        right_bar = cv2.putText(right_bar, str_current_score, (pos_x, pos_y), font, 
                   1, color, 2, cv2.LINE_AA)
        
        str_highest_score = f"Highest Score: {max_score}"
        right_bar = cv2.putText(right_bar, str_highest_score, (pos_x, pos_y + 50), font, 
                   1, color, 1, cv2.LINE_AA)
        
        return right_bar
    
    def exit_program(self):
        self.safe_the_high_score(self.PATH_TO_HIGH_SCORE)
        self._capture.release()
        cv2.destroyAllWindows()
        exit(0) 

    def safe_the_high_score(self, path):
        try:
            with open(path, 'r') as reader:
                high_score = reader.readline()
        except FileNotFoundError:
            return
            
        try:
            high_score = int(high_score)
            if self._highest_score > high_score:
                try:
                    with open(path, 'w') as writer:
                        writer.write(str(self._highest_score))
                except FileNotFoundError:
                    return
        except ValueError:
            return

    def show_menu(self):
        cv2.namedWindow(self.PROGRAM_NAME)
        # read to self._raw_frame because this picture need to be display until the camera frame is ready
        self._raw_frame = cv2.imread(self.FIRST_FRAME_PATH)
        if self._raw_frame is not None and self._raw_right_menu is not None:
            canvas = self.concate_camera_frame_with_menu(camera_frame=self._raw_frame, right_bar=self._raw_right_menu)
            cv2.imshow(self.PROGRAM_NAME, canvas)
        else:
            exit(1)

    def concate_camera_frame_with_menu(self, camera_frame, right_bar):
        window_width = right_bar.shape[1] + camera_frame.shape[1]
        canvas = np.zeros((max(right_bar.shape[0], camera_frame.shape[0]), window_width, 3), dtype=np.uint8)    
        # Place the camera frame on the left side of the canvas
        canvas[:camera_frame.shape[0], :camera_frame.shape[1]] = camera_frame
        # Place the menu bar on the right side of the canvas
        canvas[:right_bar.shape[0], camera_frame.shape[1]:] = right_bar
        return canvas
        
    def find_human_pose_in_image(self, raw_camera_frame):
        # Recolor image because mediapipe need RGB,
        # and cv2 has default BGR
        image = cv2.cvtColor(raw_camera_frame, cv2.COLOR_BGR2RGB)
        # Memory optimization
        image.flags.writeable = False

        # Make detection
        pose_detection_results = self.POSE_DETECTOR.process(image)
        return pose_detection_results

    def draw_the_body_landmarks(self):
        try:
            mp.solutions.drawing_utils.draw_landmarks(
                self.frame,
                self.pose_detection_results.pose_landmarks,
                mp.solutions.pose.POSE_CONNECTIONS,
            )
        except Exception:
            sys.exit("Error in draw_the_body_landmarks probably run before detection")

    def get_body_part_window_coordinate(self, body_index, landmarks, camera_frame):
        body_part = landmarks[body_index.value]
        x = round(body_part.x * camera_frame.shape[1])
        y = round(body_part.y * camera_frame.shape[0])
        return x, y

    def draw_action_hand(self, action_hand, camera_frame, landmarks):
        x, y = self.get_body_part_window_coordinate(body_index=action_hand, landmarks=landmarks, camera_frame=camera_frame)
        cv2.circle(camera_frame, (x, y), self.ACTION_RADIUS, (0, 255, 0), -1)
        return camera_frame

    def draw_base_body_part(self, target_body_part, camera_frame, landmarks):
        x, y = self.get_body_part_window_coordinate(body_index=target_body_part, landmarks=landmarks, camera_frame=camera_frame)
        cv2.circle(camera_frame, (x, y), self.ACTION_RADIUS, (255, 0, 0), -1)
        return camera_frame
        
    def done_what_simon_said(self, active_hand, target_body_part, landmarks, camera_frame):
        active_x, active_y = self.get_body_part_window_coordinate(body_index=active_hand, landmarks=landmarks, camera_frame=camera_frame)
        target_x, target_y = self.get_body_part_window_coordinate(body_index=target_body_part, landmarks=landmarks, camera_frame=camera_frame)
        
        distance = math.dist(
            [active_x, active_y],
            [target_x, target_y])
        
        return distance < self.ACTION_RADIUS
        
    def regenerate_simon_instruction(self):
        active_hand = random.choice([
            self.MP_POSE.LEFT_INDEX,
            self.MP_POSE.RIGHT_INDEX
        ])
        
        if active_hand == self.MP_POSE.LEFT_INDEX:
            target_body_part = random.choice([
                self.MP_POSE.NOSE,
                self.MP_POSE.RIGHT_SHOULDER,
                self.MP_POSE.RIGHT_INDEX,
                self.MP_POSE.RIGHT_ELBOW
            ])
        elif active_hand == self.MP_POSE.RIGHT_INDEX:
            target_body_part = random.choice([
                self.MP_POSE.NOSE,
                self.MP_POSE.LEFT_SHOULDER,
                self.MP_POSE.LEFT_INDEX,
                self.MP_POSE.LEFT_ELBOW
            ])
            
        return active_hand, target_body_part
            
        
            
