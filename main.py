import sys
import ffmpeg
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QSlider, QStyle, QLabel, QMessageBox, QLineEdit, QCheckBox, QComboBox, QGroupBox
import os
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, Qt
import re

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('간편 동영상 커터')
        self.resize(800, 600)

        self.start_time = 0
        self.end_time = 0
        self.current_file_path = ""

        # Media Player, Audio Output and Video Widget
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        video_widget = QVideoWidget(self)
        self.media_player.setVideoOutput(video_widget)

        # --- File Info --- 
        self.file_info_group = QGroupBox("파일 정보")
        self.file_info_label = QLabel("파일을 열어주세요.")
        file_info_layout = QVBoxLayout()
        file_info_layout.addWidget(self.file_info_label)
        self.file_info_group.setLayout(file_info_layout)

        # --- Playback Controls ---
        self.play_pause_button = QPushButton()
        self.play_pause_button.setEnabled(False)
        self.play_pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_pause_button.clicked.connect(self.play_pause_video)

        self.current_time_label = QLabel("00:00:00.000")
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_media_position)
        self.duration_label = QLabel("00:00:00.000")

        playback_controls_layout = QHBoxLayout()
        playback_controls_layout.addWidget(self.play_pause_button)
        playback_controls_layout.addWidget(self.current_time_label)
        playback_controls_layout.addWidget(self.position_slider)
        playback_controls_layout.addWidget(self.duration_label)

        # --- Cutting Controls ---
        self.start_time_input = QLineEdit("00:00:00.000")
        start_button = QPushButton("시작 지점 설정")
        start_button.clicked.connect(self.set_start_time)

        self.end_time_input = QLineEdit("00:00:00.000")
        end_button = QPushButton("종료 지점 설정")
        end_button.clicked.connect(self.set_end_time)
        
        cut_button = QPushButton("자르기")
        cut_button.clicked.connect(self.cut_video)

        cutting_controls_layout = QHBoxLayout()
        cutting_controls_layout.addWidget(start_button)
        cutting_controls_layout.addWidget(self.start_time_input)
        cutting_controls_layout.addStretch()
        cutting_controls_layout.addWidget(end_button)
        cutting_controls_layout.addWidget(self.end_time_input)
        cutting_controls_layout.addStretch()
        cutting_controls_layout.addWidget(cut_button)

        # --- Track Controls ---
        self.video_track_checkbox = QCheckBox("영상 트랙")
        self.video_track_checkbox.setChecked(True)
        self.video_track_checkbox.toggled.connect(self.toggle_video_track)
        self.audio_track_checkbox = QCheckBox("사운드 트랙")
        self.audio_track_checkbox.setChecked(True)
        self.audio_track_checkbox.toggled.connect(self.toggle_audio_track)

        track_controls_layout = QHBoxLayout()
        track_controls_layout.addWidget(self.video_track_checkbox)
        track_controls_layout.addWidget(self.audio_track_checkbox)

        # --- Audio Codec Controls ---
        audio_codec_label = QLabel("오디오 코덱:")
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["원본 코덱 유지", "WMP 호환 코덱 (AAC)"])
        
        audio_options_layout = QHBoxLayout()
        audio_options_layout.addWidget(audio_codec_label)
        audio_options_layout.addWidget(self.audio_codec_combo)
        audio_options_layout.addStretch()


        # --- Main Layout ---
        open_button = QPushButton('파일 열기')
        open_button.clicked.connect(self.open_file_dialog)

        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(video_widget)
        layout.addWidget(self.file_info_group)
        layout.addLayout(playback_controls_layout)
        layout.addLayout(cutting_controls_layout)
        layout.addLayout(track_controls_layout)
        layout.addLayout(audio_options_layout)
        layout.addWidget(open_button)

        # --- Connect signals ---
        self.media_player.playbackStateChanged.connect(self.update_play_button_icon)
        self.media_player.positionChanged.connect(self.update_slider_position)
        self.media_player.positionChanged.connect(self.update_time_labels)
        self.media_player.durationChanged.connect(self.update_slider_range)
        self.media_player.durationChanged.connect(self.update_duration_label)

    def format_time(self, ms):
        s = ms / 1000
        mins = int(s / 60)
        s = s % 60
        h = int(mins / 60)
        mins = mins % 60
        return f"{h:02d}:{mins:02d}:{s:06.3f}"
    
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
                self.video_track_checkbox.setChecked(True)
                self.audio_track_checkbox.setChecked(True)

                # --- Update File Info Label ---
                file_name = os.path.basename(file_path)
                duration = float(probe['format']['duration'])
                duration_str = self.format_time(duration * 1000).split('.')[0]
                
                info_text = f"<b>파일 이름:</b> {file_name}<br>"
                info_text += f"<b>길이:</b> {duration_str}<br><br>"
                info_text += "<b>스트림 정보:</b><br>"
                for stream in probe['streams']:
                    codec_type = stream.get('codec_type', 'N/A')
                    codec_name = stream.get('codec_name', 'N/A')
                    info_text += f"- {codec_type.capitalize()}: {codec_name}<br>"
                self.file_info_label.setText(info_text)

            except ffmpeg.Error as e:
                QMessageBox.critical(self, "FFmpeg 오류", f"파일 분석 중 오류가 발생했습니다.\n\n{e.stderr.decode()}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일을 여는 중 알 수 없는 오류가 발생했습니다.\n{str(e)}")

    def play_pause_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def update_play_button_icon(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def update_slider_position(self, position):
        self.position_slider.setValue(position)

    def update_time_labels(self, position):
        self.current_time_label.setText(self.format_time(position))

    def update_slider_range(self, duration):
        self.position_slider.setRange(0, duration)

    def update_duration_label(self, duration):
        self.duration_label.setText(self.format_time(duration))

    def set_media_position(self, position):
        self.media_player.setPosition(position)

    def set_start_time(self):
        self.start_time = self.media_player.position()
        self.start_time_input.setText(self.format_time(self.start_time))

    def set_end_time(self):
        self.end_time = self.media_player.position()
        self.end_time_input.setText(self.format_time(self.end_time))

    def toggle_video_track(self, checked):
        self.media_player.videoOutput().setVisible(checked)

    def toggle_audio_track(self, checked):
        self.audio_output.setMuted(not checked)

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

        if video_on and not audio_on:
            file_filter = "MP4 Video (*.mp4)"
        elif not video_on and audio_on:
            file_filter = "MP3 Audio (*.mp3)"
        else: # Both on
            file_filter = "MP4 Video (*.mp4)"

        output_path, _ = QFileDialog.getSaveFileName(self, "잘라낸 파일 저장", filter=file_filter)

        if not output_path:
            return # User cancelled

        try:
            input_stream = ffmpeg.input(self.current_file_path, ss=(start_time_ms / 1000), to=(end_time_ms / 1000))

            if video_on and not audio_on:
                # Video only, no audio
                output_stream = ffmpeg.output(input_stream.video, output_path, vcodec='copy')
            elif not video_on and audio_on:
                # Audio only, no video
                output_stream = ffmpeg.output(input_stream.audio, output_path, acodec='mp3', vn=True)
            else: # Both video and audio
                audio_codec = 'copy' if self.audio_codec_combo.currentText() == "원본 코덱 유지" else 'aac'
                output_stream = ffmpeg.output(input_stream, output_path, vcodec='copy', acodec=audio_codec)

            ffmpeg.run(output_stream, overwrite_output=True, quiet=True)
            QMessageBox.information(self, "성공", f"파일이 성공적으로 저장되었습니다:\n{output_path}")
        except ffmpeg.Error as e:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("FFmpeg 오류")
            msg.setInformativeText("동영상 처리 중 오류가 발생했습니다.")
            msg.setDetailedText(e.stderr.decode())
            msg.exec()
        except Exception as e:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("오류")
            msg.setInformativeText("알 수 없는 오류가 발생했습니다.")
            msg.setDetailedText(str(e))
            msg.exec()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
