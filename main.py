import sys
import ffmpeg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QFileDialog, QSlider, QStyle, QLabel, QMessageBox, QLineEdit, 
                            QCheckBox, QComboBox, QGroupBox, QProgressBar, QFrame, QSizePolicy,
                            QScrollArea, QMainWindow)
import os
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor
import re
import subprocess
import threading

class FFmpegWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, input_path, output_path, start_time, end_time, video_on, audio_on, audio_codec):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.start_time = start_time
        self.end_time = end_time
        self.video_on = video_on
        self.audio_on = audio_on
        self.audio_codec = audio_codec
        self.duration = end_time - start_time
        
    def run(self):
        try:
            input_stream = ffmpeg.input(self.input_path, ss=self.start_time, to=self.end_time)
            
            if self.video_on and not self.audio_on:
                output_stream = ffmpeg.output(input_stream.video, self.output_path, vcodec='copy')
            elif not self.video_on and self.audio_on:
                output_stream = ffmpeg.output(input_stream.audio, self.output_path, acodec='mp3', vn=True)
            else:
                audio_codec = 'copy' if self.audio_codec == "원본 코덱 유지" else 'aac'
                output_stream = ffmpeg.output(input_stream, self.output_path, vcodec='copy', acodec=audio_codec)
            
            # Run with progress monitoring
            process = ffmpeg.run_async(output_stream, overwrite_output=True, pipe_stderr=True)
            
            # Monitor progress
            while True:
                output = process.stderr.readline()
                if output == b'' and process.poll() is not None:
                    break
                if output:
                    line = output.decode('utf-8').strip()
                    if 'time=' in line:
                        time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                        if time_match:
                            h, m, s = time_match.groups()
                            current_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                            progress = min(int((current_seconds / self.duration) * 100), 100)
                            self.progress.emit(progress)
            
            if process.returncode == 0:
                self.finished.emit(self.output_path)
            else:
                self.error.emit("FFmpeg 처리 중 오류가 발생했습니다.")
                
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('🎬 간편 동영상 커터')
        
        # Get screen size and adjust window size accordingly
        self.adjust_window_size()
        
        # Set minimum size
        self.setMinimumSize(900, 600)

        self.start_time = 0
        self.end_time = 0
        self.current_file_path = ""
        self.is_slider_pressed = False
        self.ffmpeg_worker = None
        
        # Apply modern styling
        self.apply_styles()

        # Media Player, Audio Output and Video Widget
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget(self)
        
        # Adjust video widget size based on screen
        screen = QApplication.primaryScreen()
        screen_height = screen.availableGeometry().height()
        video_height = min(int(screen_height * 0.4), 450)  # 40% of screen height, max 450px
        
        self.video_widget.setMinimumHeight(video_height)
        self.video_widget.setMaximumHeight(video_height + 50)
        self.video_widget.setStyleSheet("""
            QVideoWidget {
                background-color: #1e1e1e;
                border: 3px solid #3d3d3d;
                border-radius: 12px;
            }
        """)
        self.media_player.setVideoOutput(self.video_widget)

        # --- File Info --- 
        self.file_info_group = QGroupBox("📁 파일 정보")
        self.file_info_group.setMaximumHeight(100)
        self.file_info_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4a90e2;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f8f9fa;
                max-height: 100px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #4a90e2;
            }
        """)
        
        # Create labels for 2-column layout
        self.file_basic_info_label = QLabel("📂 파일을 열어주세요.")
        self.file_basic_info_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: transparent;
                color: #333;
                font-size: 11px;
            }
        """)
        
        self.file_stream_info_label = QLabel("")
        self.file_stream_info_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: transparent;
                color: #333;
                font-size: 11px;
            }
        """)
        
        # 2-column layout for file info
        file_info_layout = QHBoxLayout()
        file_info_layout.addWidget(self.file_basic_info_label, 1)
        file_info_layout.addWidget(self.file_stream_info_label, 1)
        self.file_info_group.setLayout(file_info_layout)

        # --- Playback Controls ---
        playback_group = QGroupBox("🎮 재생 컨트롤")
        playback_group.setMinimumHeight(120)
        playback_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 3px solid #28a745;
                border-radius: 12px;
                margin-top: 10px;
                padding-top: 20px;
                padding-bottom: 15px;
                background-color: #f8fff8;
                min-height: 120px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #28a745;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        # Media control buttons
        self.play_pause_button = QPushButton("▶️ 재생")
        self.play_pause_button.setEnabled(False)
        self.play_pause_button.setFixedSize(120, 60)
        self.play_pause_button.clicked.connect(self.play_pause_video)
        self.play_pause_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                border: 3px solid #1e7e34;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #218838;
                border-color: #155724;
                transform: scale(1.05);
            }
            QPushButton:disabled {
                background-color: #6c757d;
                border-color: #495057;
                color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
                border-color: #155724;
            }
        """)

        self.stop_button = QPushButton("⏹️ 정지")
        self.stop_button.setEnabled(False)
        self.stop_button.setFixedSize(120, 60)
        self.stop_button.clicked.connect(self.stop_video)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                border: 3px solid #c82333;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #c82333;
                border-color: #bd2130;
                transform: scale(1.05);
            }
            QPushButton:disabled {
                background-color: #6c757d;
                border-color: #495057;
                color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #bd2130;
                border-color: #a71e2a;
            }
        """)

        # Volume control
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: white;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #fd7e14;
                border: 1px solid #777;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #fd7e14;
                border: 1px solid #5c5c5c;
                width: 16px;
                margin: -2px 0;
                border-radius: 8px;
            }
        """)

        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("QLabel { font-size: 16px; }")

        # Time labels with better styling
        self.current_time_label = QLabel("00:00:00")
        self.current_time_label.setStyleSheet("""
            QLabel { 
                color: #495057; 
                font-weight: bold; 
                font-family: 'Courier New', monospace;
                font-size: 13px;
                background-color: #e9ecef;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)
        self.current_time_label.setMinimumWidth(80)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.setMinimumHeight(35)
        self.position_slider.setFixedHeight(35)
        self.position_slider.sliderMoved.connect(self.set_media_position)
        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 2px solid #ced4da;
                background: #f8f9fa;
                height: 12px;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #4a90e2, stop: 1 #357abd);
                border: 2px solid #357abd;
                height: 12px;
                border-radius: 6px;
            }
            QSlider::add-page:horizontal {
                background: #f8f9fa;
                border: 2px solid #ced4da;
                height: 12px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ffffff, stop: 1 #4a90e2);
                border: 2px solid #357abd;
                width: 20px;
                margin: -4px 0;
                border-radius: 10px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ffffff, stop: 1 #357abd);
                border: 2px solid #2c5aa0;
            }
        """)
        
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setStyleSheet(self.current_time_label.styleSheet())
        self.duration_label.setMinimumWidth(80)

        # Layout for media controls
        media_buttons_layout = QHBoxLayout()
        media_buttons_layout.setSpacing(20)
        media_buttons_layout.setContentsMargins(10, 5, 10, 5)
        media_buttons_layout.addWidget(self.play_pause_button)
        media_buttons_layout.addWidget(self.stop_button)
        media_buttons_layout.addStretch()
        media_buttons_layout.addWidget(volume_label)
        media_buttons_layout.addWidget(self.volume_slider)

        # Layout for time and position
        time_layout = QHBoxLayout()
        time_layout.setSpacing(10)
        time_layout.setContentsMargins(10, 5, 10, 5)
        time_layout.addWidget(self.current_time_label)
        time_layout.addWidget(self.position_slider)
        time_layout.addWidget(self.duration_label)

        # Combine layouts
        playback_controls_layout = QVBoxLayout()
        playback_controls_layout.setSpacing(10)
        playback_controls_layout.addLayout(media_buttons_layout)
        playback_controls_layout.addLayout(time_layout)
        
        playback_group.setLayout(playback_controls_layout)

        # --- Cutting Controls ---
        cutting_group = QGroupBox("✂️ 자르기 설정")
        cutting_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dc3545;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fff8f8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #dc3545;
            }
        """)
        
        self.start_time_input = QLineEdit("00:00:00")
        self.start_time_input.setFixedWidth(100)
        self.start_time_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                text-align: center;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
                background-color: #f8f9ff;
            }
        """)
        
        start_button = QPushButton("📍 현재 위치를\n시작점으로")
        start_button.clicked.connect(self.set_start_time)
        start_button.setFixedSize(120, 50)
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #138496;
                transform: scale(1.02);
            }
        """)

        self.end_time_input = QLineEdit("00:00:00")
        self.end_time_input.setStyleSheet(self.start_time_input.styleSheet())
        
        end_button = QPushButton("🏁 현재 위치를\n종료점으로")
        end_button.clicked.connect(self.set_end_time)
        end_button.setFixedSize(120, 50)
        end_button.setStyleSheet(start_button.styleSheet())
        
        self.cut_button = QPushButton("✂️ 자르기 시작")
        self.cut_button.clicked.connect(self.cut_video)
        self.cut_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)

        cutting_controls_layout = QHBoxLayout()
        cutting_controls_layout.addWidget(start_button)
        cutting_controls_layout.addWidget(self.start_time_input)
        cutting_controls_layout.addStretch()
        cutting_controls_layout.addWidget(end_button)
        cutting_controls_layout.addWidget(self.end_time_input)
        cutting_controls_layout.addStretch()
        cutting_controls_layout.addWidget(self.cut_button)
        
        cutting_group.setLayout(cutting_controls_layout)

        # --- Output Path Controls ---
        output_group = QGroupBox("💾 저장 설정")
        output_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #6f42c1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #faf8ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #6f42c1;
            }
        """)
        
        output_path_label = QLabel("📂 저장 위치:")
        output_path_label.setStyleSheet("QLabel { font-weight: bold; color: #495057; }")
        
        self.output_path_input = QLineEdit()
        self.output_path_input.setReadOnly(True)
        self.output_path_input.setPlaceholderText("저장할 폴더를 선택해주세요...")
        self.output_path_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
        """)
        
        browse_output_button = QPushButton("📁 찾아보기")
        browse_output_button.clicked.connect(self.browse_output_directory)
        browse_output_button.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)

        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(output_path_label)
        output_path_layout.addWidget(self.output_path_input)
        output_path_layout.addWidget(browse_output_button)
        
        output_group.setLayout(output_path_layout)

        # --- Track Controls ---
        options_group = QGroupBox("⚙️ 출력 옵션")
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #fd7e14;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fff9f5;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #fd7e14;
            }
        """)
        
        self.video_track_checkbox = QCheckBox("🎬 영상 트랙")
        self.video_track_checkbox.setChecked(True)
        self.video_track_checkbox.toggled.connect(self.toggle_video_track)
        self.video_track_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #495057;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ced4da;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #28a745;
                background-color: #28a745;
                border-radius: 3px;
            }
        """)
        
        self.audio_track_checkbox = QCheckBox("🔊 사운드 트랙")
        self.audio_track_checkbox.setChecked(True)
        self.audio_track_checkbox.toggled.connect(self.toggle_audio_track)
        self.audio_track_checkbox.setStyleSheet(self.video_track_checkbox.styleSheet())

        track_controls_layout = QHBoxLayout()
        track_controls_layout.addWidget(self.video_track_checkbox)
        track_controls_layout.addWidget(self.audio_track_checkbox)
        track_controls_layout.addStretch()

        # --- Audio Codec Controls ---
        audio_codec_label = QLabel("🎵 오디오 코덱:")
        audio_codec_label.setStyleSheet("QLabel { font-weight: bold; color: #495057; }")
        
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["원본 코덱 유지", "WMP 호환 코덱 (AAC)"])
        self.audio_codec_combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                min-width: 150px;
            }
            QComboBox:focus {
                border-color: #4a90e2;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        
        audio_options_layout = QHBoxLayout()
        audio_options_layout.addWidget(audio_codec_label)
        audio_options_layout.addWidget(self.audio_codec_combo)
        audio_options_layout.addStretch()
        
        options_layout = QVBoxLayout()
        options_layout.addLayout(track_controls_layout)
        options_layout.addLayout(audio_options_layout)
        options_group.setLayout(options_layout)
        
        # --- Progress Bar ---
        self.progress_group = QGroupBox("📊 진행 상황")
        self.progress_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #20c997;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f0fff4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #20c997;
            }
        """)
        self.progress_group.setVisible(False)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ced4da;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #20c997;
                border-radius: 6px;
            }
        """)
        
        self.progress_label = QLabel("준비 중...")
        self.progress_label.setStyleSheet("QLabel { color: #495057; font-weight: bold; }")
        
        progress_layout = QVBoxLayout()
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        self.progress_group.setLayout(progress_layout)


        # --- Main Layout ---
        # Create central widget and scroll area
        central_widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidget(central_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)
        
        open_button = QPushButton('📁 파일 열기')
        open_button.setFixedSize(150, 50)
        open_button.clicked.connect(self.open_file_dialog)
        open_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)

        open_button_layout = QHBoxLayout()
        open_button_layout.addWidget(open_button)
        open_button_layout.addStretch()

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        central_widget.setLayout(layout)
        
        layout.addLayout(open_button_layout)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.file_info_group)
        layout.addWidget(playback_group)
        layout.addWidget(cutting_group)
        layout.addWidget(output_group)
        layout.addWidget(options_group)
        layout.addWidget(self.progress_group)


        # --- Connect signals ---
        self.media_player.playbackStateChanged.connect(self.update_play_button_icon)
        self.media_player.positionChanged.connect(self.update_slider_position)
        self.media_player.positionChanged.connect(self.update_time_labels)
        self.media_player.durationChanged.connect(self.update_slider_range)
        self.media_player.durationChanged.connect(self.update_duration_label)
        
        # Connect screen change signal
        QApplication.primaryScreen().geometryChanged.connect(self.on_screen_changed)

    def adjust_window_size(self):
        """Adjust window size based on screen resolution"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # Calculate optimal window size (80% of screen size)
        optimal_width = int(screen_width * 0.8)
        optimal_height = int(screen_height * 0.8)
        
        # Set maximum limits
        max_width = min(optimal_width, 1400)
        max_height = min(optimal_height, 1000)
        
        # Set minimum limits
        min_width = max(900, int(screen_width * 0.6))
        min_height = max(600, int(screen_height * 0.6))
        
        # Apply size
        self.resize(max_width, max_height)
        
        # Center window on screen
        x = (screen_width - max_width) // 2
        y = (screen_height - max_height) // 2
        self.move(x, y)
        
        print(f"화면 해상도: {screen_width}x{screen_height}")
        print(f"창 크기 조정: {max_width}x{max_height}")

    def apply_styles(self):
        """Apply modern styling to the application"""
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }
            QMainWindow {
                background-color: #ffffff;
            }
        """)

    def format_time(self, ms):
        s = ms / 1000
        mins = int(s / 60)
        s = s % 60
        h = int(mins / 60)
        mins = mins % 60
        return f"{h:02d}:{mins:02d}:{s:02.0f}"
    
    def parse_time(self, time_str):
        time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})\\.(\d{3})')
        match = time_pattern.match(time_str)
        if not match:
            try: # Try parsing without milliseconds
                parts = time_str.split(':')
                h = int(parts[0])
                mins = int(parts[1])
                s = float(parts[2])
                return int((h * 3600 + mins * 60 + s) * 1000)
            except (ValueError, IndexError):
                return 0 # Or raise an error

        h, mins, s, ms = map(int, match.groups())
        return (h * 3600 + mins * 60 + s) * 1000 + ms

    def open_file_dialog(self):
        file_filter = "Video Files (*.mp4 *.avi *.mkv *.mov)"
        file_path, _ = QFileDialog.getOpenFileName(self, '동영상 파일 열기', filter=file_filter)
        
        if file_path:
            try:
                probe = ffmpeg.probe(file_path)
                self.current_file_path = file_path
                self.media_player.setSource(QUrl.fromLocalFile(file_path))
                self.play_pause_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self.video_track_checkbox.setChecked(True)
                self.audio_track_checkbox.setChecked(True)
                
                # Set initial volume
                self.audio_output.setVolume(0.7)
                
                # Auto-play the video after loading
                QTimer.singleShot(500, self.media_player.play)

                # --- Update File Info Labels (2-column layout) ---
                file_name = os.path.basename(file_path)
                duration = float(probe['format']['duration'])
                duration_str = self.format_time(duration * 1000).split('.')[0]
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                
                # Basic info (left column)
                basic_info = f"<div style='color: #333; line-height: 1.3;'>"
                basic_info += f"<b style='color: #4a90e2;'>📄 파일:</b> {file_name}<br>"
                basic_info += f"<b style='color: #28a745;'>⏱️ 시간:</b> {duration_str}<br>"
                basic_info += f"<b style='color: #6f42c1;'>💾 크기:</b> {file_size_mb:.1f} MB"
                basic_info += "</div>"
                
                # Stream info (right column)
                stream_info = f"<div style='color: #333; line-height: 1.3;'>"
                stream_info += "<b style='color: #fd7e14;'>🎬 스트림 정보:</b><br>"
                
                video_streams = []
                audio_streams = []
                for stream in probe['streams']:
                    codec_type = stream.get('codec_type', 'N/A')
                    codec_name = stream.get('codec_name', 'N/A')
                    if codec_type == 'video':
                        width = stream.get('width', 'N/A')
                        height = stream.get('height', 'N/A')
                        video_streams.append(f"📹 {codec_name} ({width}x{height})")
                    elif codec_type == 'audio':
                        sample_rate = stream.get('sample_rate', 'N/A')
                        channels = stream.get('channels', 'N/A')
                        audio_streams.append(f"🔊 {codec_name} ({channels}ch)")
                
                for stream in video_streams + audio_streams:
                    stream_info += f"• {stream}<br>"
                
                stream_info += "</div>"
                
                self.file_basic_info_label.setText(basic_info)
                self.file_stream_info_label.setText(stream_info)
                
                # Show success message
                QMessageBox.information(self, "✅ 파일 로드 완료", 
                                      f"동영상이 성공적으로 로드되었습니다!\n\n"
                                      f"📁 {file_name}\n"
                                      f"⏱️ {duration_str}\n\n"
                                      f"🎬 자동으로 재생이 시작됩니다.")

            except ffmpeg.Error as e:
                QMessageBox.critical(self, "FFmpeg 오류", f"파일 분석 중 오류가 발생했습니다.\n\n{e.stderr.decode()}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일을 여는 중 알 수 없는 오류가 발생했습니다.\n{str(e)}")

    def play_pause_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_video(self):
        self.media_player.stop()

    def change_volume(self, value):
        self.audio_output.setVolume(value / 100.0)

    def update_play_button_icon(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("⏸️ 일시정지")
            self.play_pause_button.setStyleSheet("""
                QPushButton {
                    background-color: #ffc107;
                    border: 3px solid #e0a800;
                    border-radius: 15px;
                    color: #212529;
                    font-weight: bold;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #e0a800;
                    border-color: #d39e00;
                    transform: scale(1.05);
                }
                QPushButton:pressed {
                    background-color: #d39e00;
                    border-color: #b8860b;
                }
            """)
        else:
            self.play_pause_button.setText("▶️ 재생")
            self.play_pause_button.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    border: 3px solid #1e7e34;
                    border-radius: 15px;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #218838;
                    border-color: #155724;
                    transform: scale(1.05);
                }
                QPushButton:disabled {
                    background-color: #6c757d;
                    border-color: #495057;
                    color: #adb5bd;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                    border-color: #155724;
                }
            """)

    def update_slider_position(self, position):
        if not self.is_slider_pressed:
            self.position_slider.setValue(position)

    def update_time_labels(self, position):
        self.current_time_label.setText(self.format_time(position))

    def update_slider_range(self, duration):
        self.position_slider.setRange(0, duration)

    def update_duration_label(self, duration):
        self.duration_label.setText(self.format_time(duration))

    def set_media_position(self, position):
        self.media_player.setPosition(position)

    def slider_pressed(self):
        self.is_slider_pressed = True

    def slider_released(self):
        self.is_slider_pressed = False
        self.media_player.setPosition(self.position_slider.value())

    def set_start_time(self):
        self.start_time = self.media_player.position()
        formatted_time = self.format_time(self.start_time)
        self.start_time_input.setText(formatted_time)
        # Visual feedback
        self.start_time_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #28a745;
                border-radius: 4px;
                background-color: #d4edda;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                text-align: center;
                color: #155724;
            }
        """)
        QTimer.singleShot(1000, self.reset_start_time_style)

    def set_end_time(self):
        self.end_time = self.media_player.position()
        formatted_time = self.format_time(self.end_time)
        self.end_time_input.setText(formatted_time)
        # Visual feedback
        self.end_time_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #dc3545;
                border-radius: 4px;
                background-color: #f8d7da;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                text-align: center;
                color: #721c24;
            }
        """)
        QTimer.singleShot(1000, self.reset_end_time_style)

    def reset_start_time_style(self):
        self.start_time_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                text-align: center;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
                background-color: #f8f9ff;
            }
        """)

    def reset_end_time_style(self):
        self.end_time_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                text-align: center;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
                background-color: #f8f9ff;
            }
        """)

    def toggle_video_track(self, checked):
        self.media_player.videoOutput().setVisible(checked)

    def toggle_audio_track(self, checked):
        self.audio_output.setMuted(not checked)

    def browse_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택")
        if directory:
            self.output_path_input.setText(directory)

    def cut_video(self):
        if not self.current_file_path:
            QMessageBox.warning(self, "오류", "먼저 동영상 파일을 열어주세요.")
            return

        start_time_ms = self.parse_time(self.start_time_input.text())
        end_time_ms = self.parse_time(self.end_time_input.text())

        if end_time_ms <= start_time_ms:
            QMessageBox.warning(self, "오류", "종료 시간은 시작 시간보다 커야 합니다.")
            return

        video_on = self.video_track_checkbox.isChecked()
        audio_on = self.audio_track_checkbox.isChecked()

        if not video_on and not audio_on:
            QMessageBox.warning(self, "오류", "영상 또는 사운드 트랙 중 하나는 선택해야 합니다.")
            return

        output_dir = self.output_path_input.text()
        if not output_dir:
            QMessageBox.warning(self, "오류", "저장할 폴더를 먼저 선택해주세요.")
            return

        if video_on and not audio_on:
            file_filter = "MP4 Video (*.mp4)"
        elif not video_on and audio_on:
            file_filter = "MP3 Audio (*.mp3)"
        else: # Both on
            file_filter = "MP4 Video (*.mp4)"

        file_name, _ = QFileDialog.getSaveFileName(self, "잘라낸 파일 이름 입력", directory=output_dir, filter=file_filter)

        if not file_name:
            return # User cancelled

        output_path = os.path.join(output_dir, os.path.basename(file_name))

        # Show progress bar and disable cut button
        self.progress_group.setVisible(True)
        self.cut_button.setEnabled(False)
        self.cut_button.setText("⏳ 처리 중...")
        self.progress_bar.setValue(0)
        self.progress_label.setText("동영상 처리를 시작합니다...")

        # Start FFmpeg worker thread
        self.ffmpeg_worker = FFmpegWorker(
            self.current_file_path,
            output_path,
            start_time_ms / 1000,
            end_time_ms / 1000,
            video_on,
            audio_on,
            self.audio_codec_combo.currentText()
        )
        
        self.ffmpeg_worker.progress.connect(self.update_progress)
        self.ffmpeg_worker.finished.connect(self.on_cut_finished)
        self.ffmpeg_worker.error.connect(self.on_cut_error)
        self.ffmpeg_worker.start()

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(f"처리 중... {value}%")

    def on_cut_finished(self, output_path):
        """Handle successful completion"""
        self.progress_bar.setValue(100)
        self.progress_label.setText("✅ 완료!")
        self.cut_button.setEnabled(True)
        self.cut_button.setText("✂️ 자르기 시작")
        
        # Hide progress after 2 seconds
        QTimer.singleShot(2000, lambda: self.progress_group.setVisible(False))
        
        QMessageBox.information(self, "🎉 성공", f"파일이 성공적으로 저장되었습니다!\n\n📁 {output_path}")

    def on_cut_error(self, error_message):
        """Handle error during cutting"""
        self.progress_group.setVisible(False)
        self.cut_button.setEnabled(True)
        self.cut_button.setText("✂️ 자르기 시작")
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("❌ 오류")
        msg.setText("동영상 처리 중 오류가 발생했습니다.")
        msg.setInformativeText(error_message)
        msg.exec()

    def on_screen_changed(self):
        """Handle screen resolution change"""
        print("화면 해상도가 변경되었습니다. UI를 조정합니다.")
        self.adjust_window_size()

    def resizeEvent(self, event):
        """Handle window resize event"""
        super().resizeEvent(event)
        # Optionally adjust video widget size when window is resized
        if hasattr(self, 'video_widget'):
            current_height = self.height()
            new_video_height = min(int(current_height * 0.4), 450)
            self.video_widget.setMinimumHeight(new_video_height)
            self.video_widget.setMaximumHeight(new_video_height + 50)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
