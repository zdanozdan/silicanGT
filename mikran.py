#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5 import QtSql

#XML
import xml.etree.ElementTree as ET
#sqlite
import sqlite3
import datetime,timeago

import db,gt,config,silican,slack

Q1 = "SELECT * FROM current_calls LEFT JOIN users ON current_calls.calling_number = users.tel_Numer ORDER BY start_time DESC"

Q1_FILTER = "SELECT * FROM current_calls LEFT JOIN users ON current_calls.calling_number = users.tel_Numer WHERE %s ORDER BY start_time DESC"

Q2 = "SELECT * FROM history_calls LEFT JOIN users ON history_calls.calling_number = users.tel_Numer ORDER BY start_time DESC"

class Window(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        """Initializer."""
        super().__init__(parent)
        self.setWindowTitle("mikran.pl - integracja centrali telefonicznej")
        print("mikran.pl - integracja centrali telefonicznej")
        self.setWindowIcon(QIcon('yoda.png')) 
        self.resize(800, 600)
        self.statusBar().showMessage('mikran.pl. Ready')
        self._calling_number = "..."
        db.init_db()
        self.config = db.load_config()
        self.current_calls_columns = []
        try:
            self.current_calls_columns = db.get_columns(Q1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error",
                "Error: %s" % str(e),
            )
        try:
            db.load_slack_users()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Slack error",
                "Slack Error: %s" % str(e),
            )
        self.con = db.create_con()
        if not self.con.open():
            QtWidgets.QMessageBox.critical(
                None,
                "Database error! Sprawdź ustawienia DB",
                "Database Error: %s" % con.lastError().databaseText(),
            )
            return

        self.addModels()
        self.addViews()

        vbox = QtWidgets.QVBoxLayout()
        self.phonenumber = QtWidgets.QLabel("Czekam na nowe połączenie ....")
        font = self.phonenumber.font()
        font.setPointSize(30)
        self.phonenumber.setFont(font)
        self.phonenumber.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.phonenumber.setStyleSheet("color: gray")
        vbox.addWidget(self.phonenumber)
        
        grid = QtWidgets.QGridLayout(self)
        
        grid.addWidget(QtWidgets.QLabel("Firma:"),0,0)
        self.firma = QtWidgets.QLabel("...")
        policy = self.firma.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        self.firma.setSizePolicy(policy)
        grid.addWidget(self.firma,0,1)

        grid.addWidget(QtWidgets.QLabel("Adres:"),1,0)
        self.adres = QtWidgets.QLabel("...")
        grid.addWidget(self.adres,1,1)

        grid.addWidget(QtWidgets.QLabel("NIP:"),2,0)
        self.nip = QtWidgets.QLabel("...")
        grid.addWidget(self.nip,2,1)
        vbox.addLayout(grid)
        self.addTabs(vbox)

        self.pbar = QtWidgets.QProgressBar(self)
        self.pbar.setValue(0)
        vbox.addWidget(self.pbar)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(vbox)
        self.setCentralWidget(self.widget)
        
        #self.createToolBar()
        self.createMenuBar()
        self.createSettingsWigdet()
        self.start_threads()

    def createMenuBar(self):
        usersAction = QtWidgets.QAction(QIcon('download.png'), '&Pobierz kontrahentów', self)
        usersAction.setShortcut('Ctrl+P')
        usersAction.setStatusTip('Pobierz konkrahentów z baz danych')
        usersAction.triggered.connect(self.usersActionThread)

        historyAction = QtWidgets.QAction(QIcon('history.png'), '&Pobierz historię (wew: '+self.config['login']+')', self)
        historyAction.setShortcut('Ctrl+I')
        historyAction.setStatusTip('Pobierz historię dla tego numeru wew')
        historyAction.triggered.connect(self.historyActionThread)

        settingsAction = QtWidgets.QAction(QIcon('settings.png'), '&Ustawienia', self)
        settingsAction.setShortcut('Ctrl+U')
        settingsAction.setStatusTip('UStawienia')
        settingsAction.triggered.connect(self.settings)
        
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&Plik')
        fileMenu.addAction(usersAction)
        fileMenu.addAction(historyAction)
        fileMenu.addAction(settingsAction)

    def usersActionThread(self):
        gt_thread = gt.GTThread(parent=self)
        gt_thread._signal.connect(self.signal_gt)
        gt_thread.start()
        self.statusBar().setStyleSheet("color: green")
        self.statusBar().showMessage('Pobieranie listy kontrahentów ....')

    def historyActionThread(self):
        silican_history_thread = silican.SilicanHistoryThread(parent=self)
        silican_history_thread._signal.connect(self.signal_silican)
        silican_history_thread.start()

    def start_threads(self):
        silican_thread = silican.SilicanConnectionThread(parent=self)
        silican_thread._signal.connect(self.signal_silican)
        silican_thread.start()

    def signal_silican(self,data):
        if data[0] == config.SILICAN_CONNECTED:
            self.statusBar().showMessage('Centrala podłączona')
        if data[0] == config.SILICAN_ERROR:
            self.statusBar().setStyleSheet("color: red")
            self.statusBar().showMessage('Nie udało się podłączyć do centrali')
            QtWidgets.QMessageBox.critical(
                None,
                "Błąd podczas łączenia do centrali %s" % data[1],
                "Błąd podczas łączenia do centrali %s" % data[1],
            )

        if data[0] == config.SILICAN_USER_FOUND:
            adres = (data[1]['adr_Adres'],data[1]['adr_Miejscowosc'],data[1]['pa_Nazwa'])
            self.firma.setText(data[1]['adr_NazwaPelna'])
            self.firma.setStyleSheet("color: green")
            self.adres.setText(",".join(adres))
            self.adres.setStyleSheet("color: green")
            self.nip.setText(data[1]['adr_NIP'])
            self.nip.setStyleSheet("color: green")
            
        if data[0] == config.SILICAN_CONNECTION:
            self.phonenumber.setStyleSheet("color: green")
            self.phonenumber.setText("Nowe połączenie: %s" % data[1])
            self.firma.setText("...")
            self.adres.setText("...")
            self.nip.setText("...")
            self._calling_number = data[1]

        if data[0] == config.SILICAN_RELEASE:
            self.phonenumber.setText("Zakończono: %s" % self._calling_number)
            self.phonenumber.setStyleSheet("color: gray")
            self.firma.setStyleSheet("color: gray")
            self.adres.setStyleSheet("color: gray")
            self.nip.setStyleSheet("color: gray")

        if data[0] == config.SILICAN_SQL:
            query = QtSql.QSqlQuery()
            query.exec(data[1])
            self.calls_model.setQuery(QtSql.QSqlQuery(Q1))
            self.calls_model.select()

        if data[0] == config.SILICAN_PROGRESS:            
            self.pbar.setValue(int(data[1]))

        if data[0] == config.SILICAN_SETRANGE:
            self.pbar.setMaximum(int(data[1]))

        if data[0] == config.SILICAN_HISTORY_SQL:
            query = QtSql.QSqlQuery()
            query.exec(data[1])
            self.history_model.setQuery(QtSql.QSqlQuery(Q2))
            self.history_model.select()

    def signal_gt(self,data):
        if data[0] == config.ODBC_ERROR:
            QtWidgets.QMessageBox.critical(
                None,
                "GT connection error %s" % data[1],
                "GT connection error %s" % data[1],
            )

        if data[0] == config.ODBC_SUCCESS:
            self.users_model.setTable("users")
            self.users_model.select()
            self.statusBar().setStyleSheet("color: green")
            self.statusBar().showMessage("Pobrano kartoteki klientów")
            QtWidgets.QMessageBox.information(
                None,
                "Pobrano kartotetki klientów: %s" % data[1],
                "Pobrano kartoteki klientów: %s" % data[1],
            )

        if data[0] == config.ODBC_INSERT:
            self.pbar.setValue(int(data[1]))

        if data[0] == config.ODBC_INSERT_SETRANGE:
            self.pbar.setMaximum(int(data[1]))

        if data[0] == config.ODBC_SQL:
            query = QtSql.QSqlQuery()
            query.exec(data[1])

    def addModels(self):
        self.users_model = MikranTableModel(config=self.config)
        self.users_model.setTable("users")
        self.users_model.select()

        self.calls_model = MikranTableModel(config=self.config)
        self.calls_model.setQuery(QtSql.QSqlQuery(Q1))
        self.calls_model.select()

        self.history_model = MikranTableModel(config=self.config)
        self.history_model.setQuery(QtSql.QSqlQuery(Q2))
        self.history_model.select()

    def addViews(self):
        self.tableview_history = QtWidgets.QTableView()
        self.tableview_history.setAlternatingRowColors(True);
        self.tableview_history.setModel(self.history_model)
        self.tableview_history.resizeColumnsToContents()
        self.tableview_history.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_history.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_history.setSortingEnabled(True)
        self.tableview_history.setWordWrap(True);
        self.tableview_history.hideColumn(0)
        self.tableview_history.update()
        
        self.tableview_users = QtWidgets.QTableView()
        self.tableview_users.setAlternatingRowColors(True);
        #self.tableview_users.setStyleSheet("alternate-background-color: yellow;background-color: red;");
        self.tableview_users.setModel(self.users_model)
        self.tableview_users.resizeColumnsToContents()
        self.tableview_users.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_users.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_users.setSortingEnabled(True)
        self.tableview_users.setWordWrap(True);
        self.tableview_users.hideColumn(0)
        self.tableview_users.update()
        self.users_columns = {self.tableview_users.model().headerData(x, QtCore.Qt.Horizontal):x for x in range(self.tableview_users.model().columnCount())}

        self.tableview_calls = CallsTableView(self.current_calls_columns)
        self.tableview_calls.setAlternatingRowColors(True);
        self.tableview_calls.setModel(self.calls_model)
        self.tableview_calls.resizeColumnsToContents()
        self.tableview_calls.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.tableview_calls.sortByColumn(0, Qt.AscendingOrder);
        self.tableview_calls.setSortingEnabled(True)
        self.tableview_calls.setWordWrap(True);
        self.tableview_calls.update()
        self.calls_columns = {self.tableview_calls.model().headerData(x, QtCore.Qt.Horizontal):x for x in range(self.tableview_calls.model().columnCount())}

        self.tableview_calls.hideColumn(self.calls_columns['cr'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_id'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_CountryCode'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_CountryCode'])
        self.tableview_calls.hideColumn(self.calls_columns['tel_Numer'])
        self.tableview_calls.hideColumn(self.calls_columns['pa_Nazwa'])
        self.tableview_calls.hideColumn(self.calls_columns['adr_Adres'])

        self.tableview_calls.model().setHeaderData(self.calls_columns['start_time'], Qt.Horizontal, "Czas i data")
        self.tableview_calls.model().setHeaderData(self.calls_columns['calls_state'], Qt.Horizontal, "Status")
        self.tableview_calls.model().setHeaderData(self.calls_columns['called_number'], Qt.Horizontal, "Linia")
        self.tableview_calls.model().setHeaderData(self.calls_columns['calling_number'], Qt.Horizontal, "Nr telefonu")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_NazwaPelna'], Qt.Horizontal, "Nazwa")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_NIP'], Qt.Horizontal, "NIP")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_Miejscowosc'], Qt.Horizontal, "Miejscowość")
        self.tableview_calls.model().setHeaderData(self.calls_columns['adr_Ulica'], Qt.Horizontal, "Ulica")

    def addTabs(self,vbox):
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tab3 = QtWidgets.QWidget()
        self.tabs.addTab(self.tab1,"Bieżące połączenia ( wew "+self.config['login']+" )")
        self.tabs.addTab(self.tab2,"Historyczne dla ( wew "+self.config['login']+" )")
        self.tabs.addTab(self.tab3,"Kontakty")
        vbox.addWidget(self.tabs)

        layout = QtWidgets.QVBoxLayout()
        line_edit = QtWidgets.QLineEdit()
        line_edit.textChanged.connect(self.filter_users)
        layout.addWidget(line_edit)
        layout.addWidget(self.tableview_users)
        self.tab3.setLayout(layout)

        layout_calls = QtWidgets.QVBoxLayout()
        line_edit_calls = QtWidgets.QLineEdit()
        line_edit_calls.textChanged.connect(self.filter_calls)
        layout_calls.addWidget(line_edit_calls)
        layout_calls.addWidget(self.tableview_calls)
        self.tab1.setLayout(layout_calls)

        layout_history = QtWidgets.QVBoxLayout()
        line_edit_history = QtWidgets.QLineEdit()
        #line_edit_history.textChanged.connect(self.filter_history)
        layout_history.addWidget(line_edit_history)
        layout_history.addWidget(self.tableview_history)
        self.tab2.setLayout(layout_history)
        
    def createSettingsWigdet(self):
        self.settings_widget = QtWidgets.QDialog()
        self.settings_widget.setWindowTitle("mikran.pl - ustawienia")
        self.settings_widget.setModal(True)
        model = QtSql.QSqlTableModel(self)
        model.setTable("config")  

        tableview = QtWidgets.QTableView()
        tableview.setModel(model)
        tableview.setSortingEnabled(True)
        tableview.sortByColumn(0, Qt.DescendingOrder);

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(tableview)

        btn = QtWidgets.QPushButton("Zamknij")
        btn.clicked.connect(self.settings_widget.close)
        vbox.addWidget(btn)
        
        self.settings_widget.setLayout(vbox)

    def createToolBar(self):
        toolBar = QtWidgets.QToolBar()
        self.addToolBar(toolBar)
        
        toolButton = QtWidgets.QToolButton()
        toolButton.setText("Settings")
        toolButton.clicked.connect(self.settings)
        toolBar.addWidget(toolButton)

    def settings(self):        
        self.settings_widget.show()

    def filter_calls(self,data):
        if data:
            f = " (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')"
            sql = Q1_FILTER % f
            self.calls_model.setQuery(QtSql.QSqlQuery(sql))
        else:
            self.calls_model.setQuery(QtSql.QSqlQuery(Q1))

        self.calls_model.select()
        
    def filter_users(self,data):
        if data:
            self.users_model.setFilter(" (tel_Numer like '%"+data+"%' OR pa_Nazwa like '%"+data+"%' OR adr_NazwaPelna like '%"+data+"%' OR adr_NIP like '%"+data+"%' OR adr_Miejscowosc like '%"+data+"%' OR adr_Ulica like '%"+data+"%')")
        else:
            self.users_model.setFilter("")


class CustomerDialog(QtWidgets.QDialog):
    def __init__(self,message=tuple()):
        super().__init__()
        self.message = message
        self.setWindowTitle("Wysyłka na Slack'a")
        self.createFormGroupBox()
        #QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Ignore

        button = QtWidgets.QPushButton("Slack it !")
        button.clicked.connect(self.slackit)
        
        self.buttonBox = QtWidgets.QDialogButtonBox()
        #self.buttonBox.addButton(QBtn)
        self.buttonBox.addButton(button,QtWidgets.QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Zamknij",QtWidgets.QDialogButtonBox.RejectRole)
        #self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QtWidgets.QVBoxLayout()
        #message = QtWidgets.QLabel("Tekst do wysłania:")
        #self.layout.addWidget(message)
        self.layout.addWidget(self.formGroupBox)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def createFormGroupBox(self):
        self.formGroupBox = QtWidgets.QGroupBox("Wysyłka na kanał slackowy. Żeby dodać powiadomienie <@username>")
        layout = QtWidgets.QFormLayout()
        self.textbox = QtWidgets.QPlainTextEdit(self)

        m = (self.message['start_time'],'Tel: '+self.message['calling_number'],self.message['adr_NazwaPelna'],'NIP: '+self.message['adr_NIP'],self.message['adr_Miejscowosc'],self.message['adr_Ulica'])        
        self.textbox.setPlainText("\r\n".join(m))
        
        layout.addRow(QtWidgets.QLabel("Wiadomość:"), self.textbox)
        users = slack.get_members()
        self.cb = QtWidgets.QComboBox()
        self.cb.addItem('')
        slack_users = db.slack_users_list()
        for user in slack_users:
            self.cb.addItem(user[1],user[0])
        layout.addRow(QtWidgets.QLabel("Pobudka:"), self.cb)
        layout.addRow(QtWidgets.QLabel("Kanał:"), QtWidgets.QLabel("#mikran_ogolnie"))
        self.formGroupBox.setLayout(layout)

    def slackit(self):
        message = self.textbox.toPlainText()
        mention = self.cb.itemData(self.cb.currentIndex())
        if mention:
            message = message + "\r\n" + "<@"+mention+">"

        slack.send_message(message.strip())
        QtWidgets.QMessageBox.critical(
            None,
            "Wysłano",
            "Poleciało w kanał",
        )

class MikranTableModel(QtSql.QSqlTableModel):
    def __init__(self, config):
        super(MikranTableModel, self).__init__()
        self.config = config
        self._color = QtCore.Qt.gray

    def data(self, index, role=None):
       v = QtSql.QSqlTableModel.data(self, index, role);

       if role == QtCore.Qt.BackgroundRole:
           if self._color:
               return QtGui.QBrush(self._color)

       if role == Qt.DisplayRole:
         #  self._color = QtCore.Qt.gray
           self._color = None
           if v == 'NewCall_ST':
               self._color = QtCore.Qt.yellow
               return "Nowe połączenie"
           if v == 'Connect_ST':
               self._color = QtCore.Qt.green
               return "Odebrane u mnie (%s)" % self.config['login']
           if v == 'call_intercepted':
               self._color = QtCore.Qt.green
               return "Odebrane w grupie"
           try:
               dt = datetime.datetime.strptime(v,"%m-%d-%Y, %H:%M:%S")
               v = dt.strftime("%A, %m-%d-%Y, %H:%M:%S")
           except Exception as e:
               pass
           
       return v

       
class CallsTableView(QtWidgets.QTableView):
    def __init__(self,current_calls_columns,parent=None):
        self.current_calls_columns = current_calls_columns
        super(CallsTableView,self).__init__(parent)
        
    def mouseDoubleClickEvent(self, event):
        current_row = self.currentIndex().row()
        selected = []
        
        for i in range(self.model().columnCount()):
            col = self.current_calls_columns[i]
            index = self.model().index(current_row,i)
            selected.append((col,self.model().data(index,Qt.ItemDataRole.DisplayRole)))

        dlg = CustomerDialog(dict(selected))
        dlg.exec()
            
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Enter:
            print("ENTER")
        if event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_Backspace:
            #self.model().removeRow(self.currentIndex().row())
            QtWidgets.QMessageBox.critical(
                None,
                "Delete",
                "Usunięto rekord na pozycji %d" % self.currentIndex().row(),
            )
        super(CallsTableView, self).keyPressEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec_())
