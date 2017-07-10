# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'qneat_dockwidget_base.ui'
#
# Created: Sun Jul 09 21:36:04 2017
#      by: PyQt4 UI code generator 4.10.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_QNEATDockWidgetBase(object):
    def setupUi(self, QNEATDockWidgetBase):
        QNEATDockWidgetBase.setObjectName(_fromUtf8("QNEATDockWidgetBase"))
        QNEATDockWidgetBase.resize(589, 473)
        self.dockWidgetContents = QtGui.QWidget()
        self.dockWidgetContents.setMinimumSize(QtCore.QSize(589, 0))
        self.dockWidgetContents.setObjectName(_fromUtf8("dockWidgetContents"))
        self.gridLayout = QtGui.QGridLayout(self.dockWidgetContents)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.tabWidget = QtGui.QTabWidget(self.dockWidgetContents)
        self.tabWidget.setObjectName(_fromUtf8("tabWidget"))
        self.tab = QtGui.QWidget()
        self.tab.setObjectName(_fromUtf8("tab"))
        self.gridLayout_2 = QtGui.QGridLayout(self.tab)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        self.tabWidget.addTab(self.tab, _fromUtf8(""))
        self.tab_3 = QtGui.QWidget()
        self.tab_3.setObjectName(_fromUtf8("tab_3"))
        self.tabWidget.addTab(self.tab_3, _fromUtf8(""))
        self.tab_2 = QtGui.QWidget()
        self.tab_2.setObjectName(_fromUtf8("tab_2"))
        self.tabWidget.addTab(self.tab_2, _fromUtf8(""))
        self.gridLayout.addWidget(self.tabWidget, 1, 0, 1, 1)
        self.progressBar = QtGui.QProgressBar(self.dockWidgetContents)
        self.progressBar.setProperty("value", 24)
        self.progressBar.setObjectName(_fromUtf8("progressBar"))
        self.gridLayout.addWidget(self.progressBar, 2, 0, 1, 1)
        self.groupBox = QtGui.QGroupBox(self.dockWidgetContents)
        self.groupBox.setObjectName(_fromUtf8("groupBox"))
        self.gridLayout_3 = QtGui.QGridLayout(self.groupBox)
        self.gridLayout_3.setObjectName(_fromUtf8("gridLayout_3"))
        self.label = QtGui.QLabel(self.groupBox)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout_3.addWidget(self.label, 0, 0, 1, 1)
        self.label_2 = QtGui.QLabel(self.groupBox)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout_3.addWidget(self.label_2, 2, 0, 1, 1)
        self.comboBox = QtGui.QComboBox(self.groupBox)
        self.comboBox.setObjectName(_fromUtf8("comboBox"))
        self.gridLayout_3.addWidget(self.comboBox, 1, 0, 1, 1)
        self.comboBox_2 = QtGui.QComboBox(self.groupBox)
        self.comboBox_2.setObjectName(_fromUtf8("comboBox_2"))
        self.gridLayout_3.addWidget(self.comboBox_2, 3, 0, 1, 1)
        self.gridLayout.addWidget(self.groupBox, 0, 0, 1, 1)
        QNEATDockWidgetBase.setWidget(self.dockWidgetContents)

        self.retranslateUi(QNEATDockWidgetBase)
        self.tabWidget.setCurrentIndex(2)
        QtCore.QMetaObject.connectSlotsByName(QNEATDockWidgetBase)

    def retranslateUi(self, QNEATDockWidgetBase):
        QNEATDockWidgetBase.setWindowTitle(_translate("QNEATDockWidgetBase", "QNEAT", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), _translate("QNEATDockWidgetBase", "Shortest Path", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), _translate("QNEATDockWidgetBase", "Isochrone Areas", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), _translate("QNEATDockWidgetBase", "OD Matrix", None))
        self.groupBox.setTitle(_translate("QNEATDockWidgetBase", "Input Data", None))
        self.label.setText(_translate("QNEATDockWidgetBase", "Network Layer", None))
        self.label_2.setText(_translate("QNEATDockWidgetBase", "Point Layer", None))

