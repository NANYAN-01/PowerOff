import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QLabel, QGroupBox, 
QRadioButton, QDateEdit, QTimeEdit, QPushButton, 
QVBoxLayout, QHBoxLayout, QGridLayout, QStyle, 
QSpacerItem, QSizePolicy, QMessageBox, QStackedWidget,
QSpinBox)
from PyQt5.QtCore import QDate, QTime, QTimer, QDateTime, Qt
from PyQt5.QtGui import QIcon, QFont

def resource_path(relative_path):
    """获取资源文件的绝对路径，适用于开发环境和打包后的环境"""
    try:
        # PyInstaller创建临时文件夹，并将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
 
class PowerOffWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
     
    def initUI(self):
        self.setWindowTitle("PowerOff_By lijinshan")
        self.setWindowIcon(QIcon(resource_path("app_icon.ico")))
        self.setFixedSize(580, 500)
        self.setFont(QFont("SimHei", 12))
 
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #333;
            }
 
            QGroupBox {
                font-size: 14pt;
                font-weight: bold;
                color: #0d6efd;
                border: 2px solid #0d6efd;
                border-radius: 8px;
                margin-top: 15px;
                padding: 10px 15px;
                background: white;
            }
            QGroupBox::title {
                left: 15px;
                top: -10px;
                background: white;
                padding: 0 10px;
            }
 
            QLabel#currentTimeLabel {
                background: #0d6efd;
                color: white;
                padding: 8px 15px;
                border-radius: 6px;
                font-size: 13pt;
                min-width: 200px;
                text-align: center;
            }
 
            QPushButton {
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13pt;
                color: white;
                background: #0d6efd;
                border: none;
            }
            QPushButton:hover {
                background: #0b5ed7;
            }
            QPushButton#shutdownNowBtn {
                background: #dc3545;
            }
            QPushButton#shutdownNowBtn:hover {
                background: #bb2d3b;
            }
        QPushButton#cancelBtn {
            background: #ffc107;
        }
        QPushButton#cancelBtn:hover {
            background: #e0a800;
        }
            QDateEdit, QTimeEdit, QSpinBox {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                width: 300px;
            }
            QCheckBox, QRadioButton {
                spacing: 8px;
                font-size: 12pt;
            }
        """)
 
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(20, 20, 20, 20)
        mainLayout.setSpacing(20)
 
        topLayout = QHBoxLayout()
        autoRunChk = QCheckBox("开机自启")
        self.topChk = QCheckBox("置顶")
        self.topChk.setChecked(False)
        self.timeLabel = QLabel()
        self.timeLabel.setObjectName("currentTimeLabel")
         
        topLayout.addWidget(autoRunChk)
        topLayout.addWidget(self.topChk)
        topLayout.addSpacerItem(QSpacerItem(5, 5, QSizePolicy.Expanding, QSizePolicy.Minimum))
        topLayout.addWidget(self.timeLabel)
        mainLayout.addLayout(topLayout)
 
        timeGroup = QGroupBox("设置关机时间")
        timeLayout = QVBoxLayout()
        timeLayout.setSpacing(15)
 
        methodLayout = QHBoxLayout()
        methodLayout.addWidget(QLabel("计时方式："))
        methodLayout.addStretch()
        self.specRadio = QRadioButton("指定时间")
        self.specRadio.setChecked(True)
        methodLayout.addWidget(self.specRadio)
        methodLayout.addStretch()
        self.countRadio = QRadioButton("递减方式")
        methodLayout.addWidget(self.countRadio)
        timeLayout.addLayout(methodLayout)
 
        self.stackedWidget = QStackedWidget()
         
        specTimeWidget = QWidget()
        dtGrid = QGridLayout(specTimeWidget)
        dtGrid.setSpacing(10)
        dtGrid.setAlignment(Qt.AlignLeft)
        dateLabel = QLabel("关机日期：")
        dateLabel.setStyleSheet("font-size: 14px;")
        dtGrid.addWidget(dateLabel, 0, 0, Qt.AlignRight)
        self.dateEdit = QDateEdit(QDate.currentDate())
        self.dateEdit.setDisplayFormat("yyyy年M月d日")
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setMinimumWidth(180)
        self.dateEdit.setMinimumHeight(35)
        self.dateEdit.setStyleSheet("font-size: 14px;")
        dtGrid.addWidget(self.dateEdit, 0, 1)
        timeLabel = QLabel("关机时间：")
        timeLabel.setStyleSheet("font-size: 14px;")
        dtGrid.addWidget(timeLabel, 1, 0, Qt.AlignRight)
        self.timeEdit = QTimeEdit(QTime.currentTime())
        self.timeEdit.setDisplayFormat("h:mm:ss")
        self.timeEdit.setMinimumWidth(150)
        self.timeEdit.setMinimumHeight(35)
        self.timeEdit.setStyleSheet("font-size: 14px;")
        dtGrid.addWidget(self.timeEdit, 1, 1)
        # 增加行间距
        dtGrid.setVerticalSpacing(15)
        dtGrid.setRowMinimumHeight(0, 35)
        dtGrid.setRowMinimumHeight(1, 35)
 
        countDownWidget = QWidget()
        countLayout = QHBoxLayout(countDownWidget)
        countLayout.setAlignment(Qt.AlignLeft)
        self.hourSpin = QSpinBox()
        self.hourSpin.setRange(0, 99)
        self.minSpin = QSpinBox()
        self.minSpin.setRange(0, 59)
        self.secSpin = QSpinBox()
        self.secSpin.setRange(0, 59)
        countLayout.addWidget(self.hourSpin)
        countLayout.addWidget(QLabel("小时"))
        countLayout.addSpacing(15)
        countLayout.addWidget(self.minSpin)
        countLayout.addWidget(QLabel("分钟"))
        countLayout.addSpacing(15)
        countLayout.addWidget(self.secSpin)
        countLayout.addWidget(QLabel("秒"))
         
        self.stackedWidget.addWidget(specTimeWidget)
        self.stackedWidget.addWidget(countDownWidget)
        timeLayout.addWidget(self.stackedWidget)
 
        timeGroup.setLayout(timeLayout)
        mainLayout.addWidget(timeGroup)
 
        optGroup = QGroupBox("设置关机选项")
        optLayout = QHBoxLayout()
        optLayout.setSpacing(20)
        self.shutRadio = QRadioButton("关机")
        self.shutRadio.setChecked(True)
        self.logRadio = QRadioButton("注销")
        self.rebootRadio = QRadioButton("重启")
        self.forceChk = QCheckBox("强制")
        self.forceChk.setChecked(True)
        optLayout.addStretch()
        optLayout.addWidget(self.shutRadio)
        optLayout.addStretch()
        optLayout.addWidget(self.logRadio)
        optLayout.addStretch()
        optLayout.addWidget(self.rebootRadio)
        optLayout.addStretch()
        optLayout.addWidget(self.forceChk)
        optLayout.addStretch()
        optGroup.setLayout(optLayout)
        mainLayout.addWidget(optGroup)
 
        btnLayout = QHBoxLayout()
        # 使用均匀分布的布局
        btnLayout.setSpacing(0)
        btnLayout.setContentsMargins(10, 0, 10, 0)
        
        self.okBtn = QPushButton("确定")
        self.cancelBtn = QPushButton("取消计划")
        self.cancelBtn.setObjectName("cancelBtn")
        self.nowBtn = QPushButton("立即关机")
        self.nowBtn.setObjectName("shutdownNowBtn")
        
        # 添加左右弹性空间，使三个按钮均匀分布
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.okBtn)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.cancelBtn)
        btnLayout.addStretch(1)
        btnLayout.addWidget(self.nowBtn)
        btnLayout.addStretch(1)
        
        mainLayout.addLayout(btnLayout)
 
        self.okBtn.clicked.connect(self.handle_ok)
        self.cancelBtn.clicked.connect(self.cancel_shutdown)
        self.nowBtn.clicked.connect(self.handle_shutdown_now)
        self.specRadio.toggled.connect(self.update_input_mode)
        self.topChk.stateChanged.connect(self.toggle_top)
 
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateTime)
        self.timer.start(1000)
        self.updateTime()
        self.update_input_mode()
 
    def update_input_mode(self):
        if self.specRadio.isChecked():
            self.stackedWidget.setCurrentIndex(0)
        else:
            self.stackedWidget.setCurrentIndex(1)
            
    def toggle_top(self, state):
        # 2表示选中状态，0表示未选中状态
        if state == 2:
            # 设置窗口置顶
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
        else:
            # 取消窗口置顶
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()
             
    def handle_ok(self):
        seconds = 0
        action_name, msg = "", ""
 
        if self.specRadio.isChecked():
            target_dt = QDateTime(self.dateEdit.date(), self.timeEdit.time())
            seconds = QDateTime.currentDateTime().secsTo(target_dt)
            if seconds <= 0:
                QMessageBox.warning(self, "错误", "指定时间必须晚于当前时间！")
                return
            action_name = self.get_action_name()
            msg = f"已设定计划任务：\n\n将在 {target_dt.toString('yyyy-MM-dd HH:mm:ss')} 执行 {action_name} 操作。"
        else:
            hours = self.hourSpin.value()
            minutes = self.minSpin.value()
            secs = self.secSpin.value()
            seconds = hours * 3600 + minutes * 60 + secs
            if seconds <= 0:
                QMessageBox.warning(self, "错误", "倒计时必须大于0秒！")
                return
            action_name = self.get_action_name()
            msg = f"已设定计划任务：\n\n将在 {hours} 小时 {minutes} 分钟 {secs} 秒后执行 {action_name} 操作。"
 
        self.execute_shutdown_command(seconds, msg)
 
    def handle_shutdown_now(self):
        action_name = self.get_action_name()
        reply = QMessageBox.question(self, "确认操作", f"您确定要立即{action_name}吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            msg = f"系统将立即执行 {action_name} 操作。"
            self.execute_shutdown_command(1, msg)
             
    def cancel_shutdown(self):
        os.system("shutdown -a")
        QMessageBox.information(self, "操作成功", "所有已计划的关机任务已被取消。")
 
    def execute_shutdown_command(self, seconds, msg):
        if self.shutRadio.isChecked():
            action_flag = "-s"
        elif self.rebootRadio.isChecked():
            action_flag = "-r"
        else:
            action_flag = "-l"
             
        force_flag = "-f" if self.forceChk.isChecked() else ""
         
        command = f"shutdown {action_flag} {force_flag} -t {seconds}"
        os.system(command)
        QMessageBox.information(self, "计划任务已设定", msg)
 
    def get_action_name(self):
        if self.shutRadio.isChecked():
            return "关机"
        elif self.rebootRadio.isChecked():
            return "重启"
        else:
            return "注销"
 
    def updateTime(self):
        self.timeLabel.setText(QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"))
 
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = PowerOffWidget()
    win.show()
    sys.exit(app.exec_())