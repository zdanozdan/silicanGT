from PyQt5.QtCore import QThread, pyqtSignal,Qt
import db,config
import time

class GTThread(QThread):
    _signal = pyqtSignal(tuple)
    def __init__(self,parent=None):
        super(GTThread, self).__init__(parent=parent)

#    def __del__(self):
#        self.wait()

    def run(self):
        try:
            db.load_users(self._signal)
            self._signal.emit((config.ODBC_SUCCESS,'OK'))
        except Exception as e:
            self._signal.emit((config.ODBC_ERROR,str(e)))
            #print(str(e))
