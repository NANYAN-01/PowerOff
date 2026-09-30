import sys

from PyQt5.QtCore import QSharedMemory
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QApplication

from poweroff.ui.main_window import PowerOffWidget

SHARED_KEY = "PowerOff.singleInstance"
SERVER_NAME = "PowerOff.activate"
SIGNAL_PAYLOAD = b"activate"


def notify_existing_instance():
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(300):
        return False
    socket.write(SIGNAL_PAYLOAD)
    socket.flush()
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    shared = QSharedMemory(SHARED_KEY)
    if not shared.create(1) and shared.error() == QSharedMemory.AlreadyExists:
        notify_existing_instance()
        return 0

    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    window = PowerOffWidget()

    def on_new_connection():
        connection = server.nextPendingConnection()
        if connection is not None:
            connection.readAll()
            connection.disconnectFromServer()
        window.bring_to_front()

    server.newConnection.connect(on_new_connection)
    server.listen(SERVER_NAME)

    window.show()
    exit_code = app.exec_()
    del server
    del shared
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
