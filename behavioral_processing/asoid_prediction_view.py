import os

import pandas as pd
import cv2

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QMessageBox, QPushButton

#################   W   ##################   I   ##################   P   ##################   
# Todo: Implement a custom slider that plots all the prediction on the video progress

class DLC_Frame_Finder(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASOID Prediction Viewer")
        self.setGeometry(100, 100, 1200, 960)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QVBoxLayout(self.central_widget)

        # Buttons
        self.button_layout = QtWidgets.QHBoxLayout()
        self.load_video_button = QPushButton("Load Video")
        self.load_dlc_prediction_button = QPushButton("Load Pose Estimation Used in ASOID")
        self.load_asoid_prediction_button = QPushButton("Load ASOID Prediction")

        self.button_layout.addWidget(self.load_video_button)
        self.button_layout.addWidget(self.load_dlc_prediction_button)
        self.button_layout.addWidget(self.load_asoid_prediction_button)
        self.layout.addLayout(self.button_layout)

        # Video display area
        self.video_label = QtWidgets.QLabel("No video loaded")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.layout.addWidget(self.video_label, 1)

        # Progress bar
        self.progress_layout = QtWidgets.QHBoxLayout()
        self.play_button = QPushButton("▶")
        self.play_button.setFixedWidth(20)
        self.progress_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 0) # Will be set dynamically
        self.progress_slider.setTracking(True)

        self.progress_layout.addWidget(self.play_button)
        self.progress_layout.addWidget(self.progress_slider)
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.autoplay_video)
        self.is_playing = False
        self.layout.addLayout(self.progress_layout)

        # Navigation controls
        self.navigation_group_box = QtWidgets.QGroupBox("Video Navigation")
        self.navigation_layout = QtWidgets.QGridLayout(self.navigation_group_box)

        self.prev_10_frames_button = QPushButton("Prev 10 Frames (Shift + ←)")
        self.prev_frame_button = QPushButton("Prev Frame (←)")
        self.next_frame_button = QPushButton("Next Frame (→)")
        self.next_10_frames_button = QPushButton("Next 10 Frames (Shift + →)")

        self.navigation_layout.addWidget(self.prev_10_frames_button, 0, 0)
        self.navigation_layout.addWidget(self.prev_frame_button, 0, 1)
        self.navigation_layout.addWidget(self.next_frame_button, 0, 2)
        self.navigation_layout.addWidget(self.next_10_frames_button, 0, 3)

        self.layout.addWidget(self.navigation_group_box)
        self.navigation_group_box.hide()

        # Connect buttons to events
        self.load_video_button.clicked.connect(self.load_video)
        self.load_dlc_prediction_button.clicked.connect(self.load_dlc_prediction)
        self.load_asoid_prediction_button.clicked.connect(self.load_asoid_prediction)

        self.progress_slider.sliderMoved.connect(self.set_frame_from_slider)
        self.play_button.clicked.connect(self.toggle_playback)

        self.prev_10_frames_button.clicked.connect(lambda: self.change_frame(-10))
        self.prev_frame_button.clicked.connect(lambda: self.change_frame(-1))
        self.next_frame_button.clicked.connect(lambda: self.change_frame(1))
        self.next_10_frames_button.clicked.connect(lambda: self.change_frame(10))

        QShortcut(QKeySequence(Qt.Key_Left | Qt.ShiftModifier), self).activated.connect(lambda: self.change_frame(-10))
        QShortcut(QKeySequence(Qt.Key_Left), self).activated.connect(lambda: self.change_frame(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self).activated.connect(lambda: self.change_frame(1))
        QShortcut(QKeySequence(Qt.Key_Right | Qt.ShiftModifier), self).activated.connect(lambda: self.change_frame(10))
        QShortcut(QKeySequence(Qt.Key_Space), self).activated.connect(self.toggle_playback)
        
        self.reset_state()

    def load_video(self):
        self.reset_state()
        file_dialog = QtWidgets.QFileDialog(self)
        video_path, _ = file_dialog.getOpenFileName(self, "Load Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        if video_path:
            self.original_vid = video_path
            self.initialize_loaded_video()
            self.navigation_group_box.show()

    def initialize_loaded_video(self):
        self.video_name = os.path.basename(self.original_vid).split(".")[0]
        self.cap = cv2.VideoCapture(self.original_vid)
        if not self.cap.isOpened():
            print(f"Error: Could not open video {self.original_vid}")
            self.video_label.setText("Error: Could not open video")
            self.cap = None
            return
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame_idx = 0
        self.progress_slider.setRange(0, self.total_frames - 1) # Initialize slider range
        self.display_current_frame()
        self.navigation_box_title_controller()
        print(f"Video loaded: {self.original_vid}")

    def load_dlc_prediction(self):
        if self.current_frame is None:
            QMessageBox.warning(self, "No Video", "No video has been loaded, please load a video first.")
            return
        file_dialog = QtWidgets.QFileDialog(self)
        prediction_path, _ = file_dialog.getOpenFileName(self, "Load DLC Prediction", "", "CSV Files (*.csv);;All Files (*)")
        if prediction_path:
            self.asoid_pose = prediction_path
            print(f"DLC Prediction loaded: {self.asoid_pose}")
            df = pd.read_csv(self.asoid_pose, header=[0,1,2,3])
            self.pred_frame = df.iloc[:,0].copy()

    def load_asoid_prediction(self):
        if self.current_frame is None:
            QMessageBox.warning(self, "No Video", "No video has been loaded, please load a video first.")
            return
        file_dialog = QtWidgets.QFileDialog(self)
        prediction_path, _ = file_dialog.getOpenFileName(self, "Load ASOID Prediction", "", "CSV Files (*.csv);;All Files (*)")
        if not self.asoid_pose:
            print("ASOID pose not loaded, the prediction file's frame_idx may be uncorrected")
        if prediction_path:
            self.asoid_pred = prediction_path
            print(f"ASOID Prediction loaded: {self.asoid_pred}")
            self.parse_asoid_prediction()
            self.display_current_frame()

    def parse_asoid_prediction(self):
        df = pd.read_csv(self.asoid_pred, header=[0])
        df.drop(columns='time', inplace=True)
        df["frame"] = self.pred_frame
        df.set_index("frame", inplace=True)
        self.asoid_pred_df = df

    ###################################################################################################################################################

    def display_current_frame(self):
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame
                frame = self.plot_asoid_pred(frame) if self.asoid_pred_df is not None else frame
                # Convert OpenCV image to QPixmap
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(qt_image)
                # Scale pixmap to fit label
                scaled_pixmap = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.video_label.setPixmap(scaled_pixmap)
                self.video_label.setText("") # Clear "No video loaded" text
                self.progress_slider.setValue(self.current_frame_idx) # Update slider position
            else:
                self.video_label.setText("Error: Could not read frame")
        else:
            self.video_label.setText("No video loaded")
    
    def plot_asoid_pred(self, frame):
        """
        Plots ASOID prediction on the video frame.
        If the current frame index is not in the ASOID prediction DataFrame's index,
        or if the corresponding row is all zeros, plots '---'.
        Otherwise, plots the column name(s) where the value is 1.
        """
        text_to_display = "---"
        
        if self.asoid_pred_df is not None:
            if self.current_frame_idx in self.asoid_pred_df.index:
                row = self.asoid_pred_df.loc[self.current_frame_idx]
                # Check if any value in the row is 1
                if (row == 1).any():
                    # Get column names where the value is 1
                    active_behaviors = row[row == 1].index.tolist()
                    if active_behaviors:
                        text_to_display = ", ".join(active_behaviors)
            
        # Draw text on the frame
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        font_thickness = 2
        text_color = (0, 128, 255) # Green color in BGR
        text_position = (10, 30) # Top-left corner

        cv2.putText(frame, text_to_display, text_position, font, font_scale, text_color, font_thickness, cv2.LINE_AA)
        
        return frame

    ###################################################################################################################################################

    def change_frame(self, delta):
        if self.cap and self.cap.isOpened():
            new_frame_idx = self.current_frame_idx + delta
            if 0 <= new_frame_idx < self.total_frames:
                self.current_frame_idx = new_frame_idx
                self.display_current_frame()
                self.navigation_box_title_controller()

    def set_frame_from_slider(self, value):
        if self.cap and self.cap.isOpened():
            self.current_frame_idx = value
            self.display_current_frame()
            self.navigation_box_title_controller()

    def autoplay_video(self):
        if self.cap and self.cap.isOpened():
            if self.current_frame_idx < self.total_frames - 1:
                self.current_frame_idx += 1
                self.display_current_frame()
                self.navigation_box_title_controller()
            else:
                self.playback_timer.stop()
                self.play_button.setText("▶")
                self.is_playing = False

    def toggle_playback(self):
        if self.current_frame is None:
            QMessageBox.warning(self, "No Video", "No video has been loaded, please load a video first.")
            return
        if not self.is_playing:
            self.playback_timer.start(1000/100) # 100 fps
            self.play_button.setText("■")
            self.is_playing = True
        else:
            self.playback_timer.stop()
            self.play_button.setText("▶")
            self.is_playing = False

    def navigation_box_title_controller(self):
        self.navigation_group_box.setTitle(f"Video Navigation | Frame: {self.current_frame_idx} / {self.total_frames-1} | Video: {self.video_name}")

    ###################################################################################################################################################

    def reset_state(self):
        self.original_vid, self.asoid_pose, self.asoid_pred, self.video_name = None, None, None, None
        self.total_frames = None

        self.asoid_pred_df, self.pred_frame = None, None

        self.cap, self.current_frame = None, None

        self.is_playing = False
        self.progress_slider.setRange(0, 0)
        self.navigation_group_box.hide()

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = DLC_Frame_Finder()
    window.show()
    app.exec()