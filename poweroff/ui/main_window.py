"""PowerOff 主窗口：时间设置、状态显示、系统托盘与本地倒计时执行。"""
from __future__ import annotations

import time

from PyQt5.QtCore import QDate, QDateTime, QSettings, Qt, QTime, QTimer
from PyQt5.QtGui import QFont, QFontMetrics, QIcon
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QCheckBox,
                             QDateEdit, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QMenu, QMessageBox, QPushButton,
                             QRadioButton, QSizePolicy, QSpacerItem, QSpinBox,
                             QStackedWidget, QSystemTrayIcon, QTimeEdit,
                             QVBoxLayout, QWidget)

from poweroff.core import autostart
from poweroff.core.power import (Backend, PowerAction,
                                 RC_NOTHING_TO_CANCEL, cancel,
                                 choose_backend, execute_immediate,
                                 hibernation_enabled, schedule_system)
from poweroff.core.state import (PlanState, clear_state, load_state,
                                 save_state)
from poweroff.core.util import format_duration, resource_path

BLINK_INTERVAL_MS = 500
NOTIFY_WINDOW_SECONDS = 60
PRESET_MINUTES = (5, 10, 30, 60)


def _app_settings() -> QSettings:
    return QSettings("PowerOff", "PowerOff")


class PowerOffWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plan = None
        self._blink_on = True
        self._notified = False
        self._hide_notified = False
        self.tray = None
        self.initUI()
        self.initTimers()
        self.initTray()
        self.restore_plan()

    # ---------------------------------------------------------------- UI
    def initUI(self):
        self.setWindowTitle("PowerOff_By lijinshan")
        self.setWindowIcon(QIcon(resource_path("app_icon.ico")))
        self.setFixedSize(580, 520)
        self.setFont(QFont("SimHei", 12))
        # 1.5 行行距作为各区块统一间隔
        self._gap = round(QFontMetrics(self.font()).lineSpacing() * 1.5)

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
            QLabel#currentTimeLabel[level="green"] { background: #198754; }
            QLabel#currentTimeLabel[level="yellow"] { background: #ffc107; color: #212529; }
            QLabel#currentTimeLabel[level="orange"] { background: #fd7e14; }
            QLabel#currentTimeLabel[level="red"] { background: #dc3545; }
            QLabel#currentTimeLabel[level="redDark"] { background: #4d0b12; }

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
            QPushButton#presetBtn {
                font-size: 11pt;
                padding: 4px 8px;
                background: #6c757d;
            }
            QPushButton#presetBtn:hover {
                background: #565e64;
            }
            QDateEdit, QTimeEdit {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                width: 300px;
            }
            QSpinBox {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 4px;
            }
            QCheckBox, QRadioButton {
                spacing: 8px;
                font-size: 12pt;
            }
        """)

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(20, 20, 20, 20)
        mainLayout.setSpacing(self._gap)

        topLayout = QHBoxLayout()
        self.autoRunChk = QCheckBox("开机自启")
        self.autoRunChk.setChecked(autostart.is_enabled())
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
        timeLayout.setSpacing(self._gap)

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

        presetLayout = QHBoxLayout()
        presetLayout.setSpacing(10)
        presetLayout.addWidget(QLabel("快捷倒计时："))
        self.presetButtons = []
        for minutes in PRESET_MINUTES:
            button = QPushButton("{}分".format(minutes))
            button.setObjectName("presetBtn")
            button.clicked.connect(lambda _checked=False, m=minutes: self.apply_preset(m))
            presetLayout.addWidget(button)
            self.presetButtons.append(button)
        presetLayout.addStretch()
        timeLayout.addLayout(presetLayout)

        self.stackedWidget = QStackedWidget()

        specTimeWidget = QWidget()
        dtGrid = QGridLayout(specTimeWidget)
        dtGrid.setSpacing(10)
        dtGrid.setAlignment(Qt.AlignLeft)
        dateLabel = QLabel("关机日期：")
        dtGrid.addWidget(dateLabel, 0, 0, Qt.AlignRight)
        self.dateEdit = QDateEdit(QDate.currentDate())
        self.dateEdit.setDisplayFormat("yyyy年M月d日")
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setMinimumWidth(180)
        self.dateEdit.setMinimumHeight(42)
        dtGrid.addWidget(self.dateEdit, 0, 1)
        timeLabel = QLabel("关机时间：")
        dtGrid.addWidget(timeLabel, 1, 0, Qt.AlignRight)
        self.timeEdit = QTimeEdit(QTime.currentTime())
        self.timeEdit.setDisplayFormat("h:mm:ss")
        self.timeEdit.setMinimumWidth(150)
        self.timeEdit.setMinimumHeight(42)
        dtGrid.addWidget(self.timeEdit, 1, 1)
        dtGrid.setVerticalSpacing(self._gap)
        dtGrid.setRowMinimumHeight(0, 42)
        dtGrid.setRowMinimumHeight(1, 42)

        countDownWidget = QWidget()
        countLayout = QHBoxLayout(countDownWidget)
        countLayout.setAlignment(Qt.AlignLeft)
        self.hourSpin = QSpinBox()
        self.hourSpin.setRange(0, 99)
        self.hourSpin.setFixedWidth(90)
        self.minSpin = QSpinBox()
        self.minSpin.setRange(0, 59)
        self.minSpin.setFixedWidth(90)
        self.secSpin = QSpinBox()
        self.secSpin.setRange(0, 59)
        self.secSpin.setFixedWidth(90)
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
        optLayout = QVBoxLayout()
        optLayout.setSpacing(self._gap)

        actionRow1 = QHBoxLayout()
        actionRow1.setSpacing(20)
        self.shutRadio = QRadioButton("关机")
        self.shutRadio.setChecked(True)
        self.logRadio = QRadioButton("注销")
        self.rebootRadio = QRadioButton("重启")
        self.forceChk = QCheckBox("强制")
        self.forceChk.setChecked(True)
        for widget in (self.shutRadio, self.logRadio, self.rebootRadio):
            actionRow1.addStretch()
            actionRow1.addWidget(widget)
        actionRow1.addStretch()
        actionRow1.addWidget(self.forceChk)
        actionRow1.addStretch()

        actionRow2 = QHBoxLayout()
        actionRow2.setSpacing(20)
        self.sleepRadio = QRadioButton("睡眠")
        self.hibernateRadio = QRadioButton("休眠")
        self.lockRadio = QRadioButton("锁定")
        for widget in (self.sleepRadio, self.hibernateRadio, self.lockRadio):
            actionRow2.addStretch()
            actionRow2.addWidget(widget)
        actionRow2.addStretch()

        optLayout.addLayout(actionRow1)
        optLayout.addLayout(actionRow2)
        optGroup.setLayout(optLayout)
        mainLayout.addWidget(optGroup)

        self.actionGroup = QButtonGroup(self)
        for radio in (self.shutRadio, self.logRadio, self.rebootRadio,
                      self.sleepRadio, self.hibernateRadio, self.lockRadio):
            self.actionGroup.addButton(radio)

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

        self.load_prefs()

        self.okBtn.clicked.connect(self.handle_ok)
        self.cancelBtn.clicked.connect(self.cancel_shutdown)
        self.nowBtn.clicked.connect(self.handle_shutdown_now)
        self.specRadio.toggled.connect(self.update_input_mode)
        self.topChk.stateChanged.connect(self.toggle_top)
        self.autoRunChk.toggled.connect(self.set_autostart)
        for radio in self.actionGroup.buttons():
            radio.toggled.connect(self.sync_controls)

        self.update_input_mode()
        self.sync_controls()
        self.updateTime()

        # 间隔放大后按最小高度自适应窗口，避免控件被压缩
        needed = self.layout().minimumSize().height()
        if needed > self.height():
            self.setFixedSize(580, needed)

    def initTimers(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateTime)
        self.timer.start(1000)

        self.blinkTimer = QTimer(self)
        self.blinkTimer.timeout.connect(self.toggle_blink)
        self.blinkTimer.start(BLINK_INTERVAL_MS)

    def initTray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(QIcon(resource_path("app_icon.ico")), self)
        menu = QMenu()
        showAction = menu.addAction("显示主窗口")
        cancelAction = menu.addAction("取消计划")
        menu.addSeparator()
        quitAction = menu.addAction("退出")
        showAction.triggered.connect(self.bring_to_front)
        cancelAction.triggered.connect(self.cancel_shutdown)
        quitAction.triggered.connect(self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.setToolTip("PowerOff 定时关机工具")
        self.tray.show()

    # ----------------------------------------------------------- 控件状态
    def set_autostart(self, checked):
        try:
            autostart.set_enabled(checked)
        except OSError as exc:
            QMessageBox.warning(self, "开机自启", "设置失败：{}".format(exc))
            self.autoRunChk.setChecked(autostart.is_enabled())

    def sync_controls(self):
        supports_force = self.shutRadio.isChecked() or self.rebootRadio.isChecked()
        self.forceChk.setEnabled(supports_force)

    def update_input_mode(self):
        self.stackedWidget.setCurrentIndex(0 if self.specRadio.isChecked() else 1)

    def toggle_top(self, state):
        flags = self.windowFlags()
        if state == Qt.Checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    # ----------------------------------------------------------- 计划逻辑
    def current_action(self):
        checked = self.actionGroup.checkedButton()
        mapping = {
            self.shutRadio: PowerAction.SHUTDOWN,
            self.rebootRadio: PowerAction.REBOOT,
            self.logRadio: PowerAction.LOGOFF,
            self.sleepRadio: PowerAction.SLEEP,
            self.hibernateRadio: PowerAction.HIBERNATE,
            self.lockRadio: PowerAction.LOCK,
        }
        return mapping.get(checked, PowerAction.SHUTDOWN)

    def apply_preset(self, minutes):
        self.countRadio.setChecked(True)
        self.hourSpin.setValue(minutes // 60)
        self.minSpin.setValue(minutes % 60)
        self.secSpin.setValue(0)

    def confirm_action(self, action):
        """睡眠在休眠启用时会退化为休眠，先向用户确认。"""
        if action is not PowerAction.SLEEP:
            return True
        if hibernation_enabled() is not True:
            return True
        reply = QMessageBox.question(
            self, "睡眠",
            "检测到系统启用了休眠，此睡眠操作可能实际进入休眠。仍要继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    def load_prefs(self):
        settings = _app_settings()
        mode = settings.value("mode", "spec")
        self.countRadio.setChecked(mode == "count")
        self.specRadio.setChecked(mode != "count")
        action_value = settings.value("action", PowerAction.SHUTDOWN.value)
        mapping = {
            PowerAction.SHUTDOWN.value: self.shutRadio,
            PowerAction.REBOOT.value: self.rebootRadio,
            PowerAction.LOGOFF.value: self.logRadio,
            PowerAction.SLEEP.value: self.sleepRadio,
            PowerAction.HIBERNATE.value: self.hibernateRadio,
            PowerAction.LOCK.value: self.lockRadio,
        }
        mapping.get(action_value, self.shutRadio).setChecked(True)
        self.forceChk.setChecked(bool(settings.value("force", True, type=bool)))
        if bool(settings.value("top", False, type=bool)):
            self.topChk.setChecked(True)
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

    def save_prefs(self):
        settings = _app_settings()
        settings.setValue("mode", "spec" if self.specRadio.isChecked() else "count")
        settings.setValue("action", self.current_action().value)
        settings.setValue("force", self.forceChk.isChecked())
        settings.setValue("top", self.topChk.isChecked())

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
        if not self.confirm_action(action):
            return
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
        self._notified = seconds <= NOTIFY_WINDOW_SECONDS
        self.persist_plan()
        msg = "已设定计划任务：\n\n将在 {} 执行 {} 操作。\n\n（{}）".format(
            deadline_text, action.label, scope)
        QMessageBox.information(self, "计划任务已设定", msg)

    def handle_shutdown_now(self):
        action = self.current_action()
        if not self.confirm_action(action):
            return
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
        had_plan = self.plan is not None
        had_local = had_plan and self.plan["backend"] is Backend.LOCAL
        result = cancel()
        if not result.ok and result.returncode != RC_NOTHING_TO_CANCEL:
            QMessageBox.critical(self, "取消失败", result.hint)
            return
        if had_plan:
            self.plan = None
            self.persist_plan()
        parts = []
        if had_local:
            parts.append("本程序的倒计时计划已取消。")
        parts.append("系统级关机计划已取消。" if result.ok else "系统中没有关机计划。")
        QMessageBox.information(self, "操作成功", "".join(parts))

    def fire_local_plan(self):
        plan = self.plan
        self.plan = None
        self.persist_plan()
        result = execute_immediate(plan["action"], plan["force"])
        if not result.ok:
            QMessageBox.critical(self, "执行失败", result.hint)

    # ------------------------------------------------------- 状态持久化
    def persist_plan(self):
        if self.plan is None:
            clear_state()
            return
        plan = self.plan
        save_state(PlanState(
            action=plan["action"].value,
            force=plan["force"],
            backend=plan["backend"].value,
            deadline=plan["deadline"],
            created=plan["created"],
        ))

    def restore_plan(self):
        state = load_state()
        if state is None:
            return
        try:
            action = PowerAction(state.action)
            backend = Backend(state.backend)
        except ValueError:
            clear_state()
            return
        if state.deadline <= time.time():
            clear_state()
            return
        self.plan = {
            "action": action,
            "force": state.force,
            "backend": backend,
            "deadline": state.deadline,
            "created": state.created,
        }
        self._notified = state.deadline - time.time() <= NOTIFY_WINDOW_SECONDS

    # ------------------------------------------------------- 倒计时显示
    def level_for(self, remaining):
        if remaining > 1800:
            return "green"
        if remaining > 600:
            return "yellow"
        if remaining > 60:
            return "orange"
        return "red" if self._blink_on else "redDark"

    def apply_level(self, level):
        if self.timeLabel.property("level") == level:
            return
        self.timeLabel.setProperty("level", level)
        self.style().unpolish(self.timeLabel)
        self.style().polish(self.timeLabel)

    def toggle_blink(self):
        self._blink_on = not self._blink_on
        if self.plan is None:
            return
        remaining = self.plan["deadline"] - time.time()
        if remaining <= NOTIFY_WINDOW_SECONDS:
            self.apply_level(self.level_for(max(remaining, 0)))

    def notify_soon(self):
        if self._notified:
            return
        self._notified = True
        action = self.plan["action"]
        if self.tray is not None:
            self.tray.showMessage(
                "即将执行{}".format(action.label),
                "距离执行还有不到 {} 秒，如需中止请点击“取消计划”。".format(NOTIFY_WINDOW_SECONDS),
                QSystemTrayIcon.Warning,
                8000)
        self.bring_to_front()

    def updateTime(self):
        now = time.time()
        if self.plan is not None:
            remaining = self.plan["deadline"] - now
            if remaining <= 0:
                if self.plan["backend"] is Backend.LOCAL:
                    self.fire_local_plan()
                else:
                    self.plan = None
                    self.persist_plan()
            else:
                scope = "系统" if self.plan["backend"] is Backend.SYSTEM else "本机"
                self.timeLabel.setText("剩余 {} · {} · {}".format(
                    format_duration(remaining), self.plan["action"].label, scope))
                self.apply_level(self.level_for(remaining))
                if remaining <= NOTIFY_WINDOW_SECONDS:
                    self.notify_soon()
                if self.tray is not None:
                    self.tray.setToolTip("PowerOff · 剩余 {}".format(format_duration(remaining)))
                return
        self.apply_level(None)
        self.timeLabel.setText(
            QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"))
        if self.tray is not None:
            self.tray.setToolTip("PowerOff 定时关机工具")

    # ----------------------------------------------------------- 窗口/托盘
    def bring_to_front(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.bring_to_front()

    def closeEvent(self, event):
        self.save_prefs()
        if self.tray is None:
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self._hide_notified:
            self._hide_notified = True
            self.tray.showMessage(
                "PowerOff", "程序已最小化到托盘，仍在后台运行。",
                QSystemTrayIcon.Information, 3000)

    def quit_app(self):
        self.save_prefs()
        if self.plan is not None and self.plan["backend"] is Backend.LOCAL:
            reply = QMessageBox.question(
                self, "退出",
                "仍有本机倒计时计划，退出将使其中止（系统级计划不受影响）。确定退出？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
            self.plan = None
            self.persist_plan()
        QApplication.quit()
