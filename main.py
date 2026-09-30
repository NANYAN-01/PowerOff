import os
import sys
import time

from PyQt5.QtCore import QDate, QDateTime, QSettings, Qt, QTime, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QApplication, QCheckBox, QDateEdit, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QRadioButton, QSizePolicy,
                             QSpacerItem, QSpinBox, QStackedWidget, QTimeEdit,
                             QVBoxLayout, QWidget)

from poweroff.core.power import (Backend, PowerAction,
                                 RC_NOTHING_TO_CANCEL, cancel,
                                 choose_backend, execute_immediate,
                                 schedule_system)

AUTOSTART_KEY = "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
AUTOSTART_NAME = "PowerOff"


def resource_path(relative_path):
    """获取资源文件的绝对路径，适用于开发环境和打包后的环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def _autostart_settings():
    return QSettings(AUTOSTART_KEY, QSettings.NativeFormat)


def is_autostart_enabled():
    return AUTOSTART_NAME in _autostart_settings().allKeys()


def set_autostart(enabled):
    settings = _autostart_settings()
    if not enabled:
        settings.remove(AUTOSTART_NAME)
        return
    if getattr(sys, "frozen", False):
        command = '"{}"'.format(sys.executable)
    else:
        command = '"{}" "{}"'.format(sys.executable, os.path.abspath(__file__))
    settings.setValue(AUTOSTART_NAME, command)


def format_duration(total_seconds):
    total_seconds = max(0, int(total_seconds))
    days, rest = divmod(total_seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    text = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return "{}天 {}".format(days, text) if days else text


class PowerOffWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.plan = None
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
        self.autoRunChk = QCheckBox("开机自启")
        self.autoRunChk.setChecked(is_autostart_enabled())
        self.topChk = QCheckBox("置顶")
        self.topChk.setChecked(False)
        self.timeLabel = QLabel()
        self.timeLabel.setObjectName("currentTimeLabel")

        topLayout.addWidget(self.autoRunChk)
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
        btnLayout.setSpacing(0)
        btnLayout.setContentsMargins(10, 0, 10, 0)

        self.okBtn = QPushButton("确定")
        self.cancelBtn = QPushButton("取消计划")
        self.cancelBtn.setObjectName("cancelBtn")
        self.nowBtn = QPushButton("立即执行")
        self.nowBtn.setObjectName("shutdownNowBtn")

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
        self.autoRunChk.toggled.connect(self.set_autostart)
        for radio in (self.shutRadio, self.logRadio, self.rebootRadio):
            radio.toggled.connect(self.sync_controls)

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateTime)
        self.timer.start(1000)
        self.updateTime()
        self.update_input_mode()
        self.sync_controls()

    def set_autostart(self, checked):
        try:
            set_autostart(checked)
        except OSError as exc:
            QMessageBox.warning(self, "开机自启", "设置失败：{}".format(exc))
            self.autoRunChk.setChecked(is_autostart_enabled())

    def sync_controls(self):
        """注销/睡眠等动作不支持 -t 与 -f，禁用强制勾选。"""
        supports_force = self.shutRadio.isChecked() or self.rebootRadio.isChecked()
        self.forceChk.setEnabled(supports_force)

    def update_input_mode(self):
        if self.specRadio.isChecked():
            self.stackedWidget.setCurrentIndex(0)
        else:
            self.stackedWidget.setCurrentIndex(1)

    def toggle_top(self, state):
        flags = self.windowFlags()
        if state == Qt.Checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def current_action(self):
        if self.shutRadio.isChecked():
            return PowerAction.SHUTDOWN
        if self.rebootRadio.isChecked():
            return PowerAction.REBOOT
        if self.logRadio.isChecked():
            return PowerAction.LOGOFF
        return PowerAction.SHUTDOWN

    def requested_seconds(self):
        if self.specRadio.isChecked():
            target_dt = QDateTime(self.dateEdit.date(), self.timeEdit.time())
            seconds = QDateTime.currentDateTime().secsTo(target_dt)
            if seconds <= 0:
                QMessageBox.warning(self, "错误", "指定时间必须晚于当前时间！")
                return None
            deadline_text = target_dt.toString("yyyy-MM-dd HH:mm:ss")
        else:
            seconds = (self.hourSpin.value() * 3600
                       + self.minSpin.value() * 60
                       + self.secSpin.value())
            if seconds <= 0:
                QMessageBox.warning(self, "错误", "倒计时必须大于0秒！")
                return None
            deadline_text = "{}小时{}分{}秒后".format(
                self.hourSpin.value(), self.minSpin.value(), self.secSpin.value())
        return seconds, deadline_text

    def handle_ok(self):
        requested = self.requested_seconds()
        if requested is None:
            return
        seconds, deadline_text = requested
        action = self.current_action()
        force = self.forceChk.isChecked()
        backend = choose_backend(action, force)

        if backend is Backend.SYSTEM:
            result = schedule_system(action, seconds, force)
            if not result.ok:
                QMessageBox.critical(self, "设置失败", result.hint)
                return
            scope = "系统级计划，关闭本程序后仍然生效"
        else:
            scope = "由本程序倒计时执行，请保持程序运行（可最小化到托盘）"

        self.plan = {
            "action": action,
            "force": force,
            "backend": backend,
            "deadline": time.time() + seconds,
            "created": time.time(),
        }
        msg = "已设定计划任务：\n\n将在 {} 执行 {} 操作。\n\n（{}）".format(
            deadline_text, action.label, scope)
        QMessageBox.information(self, "计划任务已设定", msg)

    def handle_shutdown_now(self):
        action = self.current_action()
        force = self.forceChk.isChecked()
        reply = QMessageBox.question(
            self, "确认操作", "您确定要立即{}吗？".format(action.label),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        result = execute_immediate(action, force)
        if not result.ok:
            QMessageBox.critical(self, "执行失败", result.hint)

    def cancel_shutdown(self):
        had_local = self.plan is not None and self.plan["backend"] is Backend.LOCAL
        if had_local:
            self.plan = None
        result = cancel()
        if not result.ok and result.returncode != RC_NOTHING_TO_CANCEL:
            QMessageBox.critical(self, "取消失败", result.hint)
            return
        parts = []
        if had_local:
            parts.append("本程序的倒计时计划已取消。")
        if result.ok:
            parts.append("系统级关机计划已取消。")
        else:
            parts.append("系统中没有关机计划。")
        QMessageBox.information(self, "操作成功", "".join(parts))

    def fire_local_plan(self):
        plan = self.plan
        self.plan = None
        result = execute_immediate(plan["action"], plan["force"])
        if not result.ok:
            QMessageBox.critical(self, "执行失败", result.hint)

    def updateTime(self):
        now = time.time()
        if self.plan is not None:
            remaining = self.plan["deadline"] - now
            if remaining <= 0:
                if self.plan["backend"] is Backend.LOCAL:
                    self.fire_local_plan()
                else:
                    self.plan = None
            else:
                scope = "系统" if self.plan["backend"] is Backend.SYSTEM else "本机"
                self.timeLabel.setText("剩余 {} · {} · {}".format(
                    format_duration(remaining), self.plan["action"].label, scope))
                return
        self.timeLabel.setText(
            QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = PowerOffWidget()
    win.show()
    sys.exit(app.exec_())
