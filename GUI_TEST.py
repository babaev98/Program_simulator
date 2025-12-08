import unittest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt, QPoint
from Ver_0_2 import MainWindow

app = QApplication([])  # Только один раз за сессию

class TestEditor(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.redactor = self.window.redactor

    def tearDown(self):
        self.window.close()

    def test_add_pump(self):
        # Выбрать элемент "QPump"
        self.window.controller.set_element("QPump")
        # Сымитировать клик мыши по сцене
        pos = QPoint(100, 100)
        QTest.mouseClick(self.redactor, Qt.LeftButton, pos=pos)
        # Проверить, что объект добавлен
        pumps = [obj for obj in self.redactor.objects if obj.tag == "Насос"]
        self.assertTrue(len(pumps) > 0)

    def test_no_overlap(self):
        # Добавить два насоса рядом
        self.window.controller.set_element("QPump")
        QTest.mouseClick(self.redactor, Qt.LeftButton, pos=QPoint(100, 100))
        self.window.controller.set_element("QPump")
        QTest.mouseClick(self.redactor, Qt.LeftButton, pos=QPoint(180, 180))  # слишком близко
        # Должен быть только один насос (второй не добавится)
        pumps = [obj for obj in self.redactor.objects if obj.tag == "Насос"]
        self.assertEqual(len(pumps), 1)

    # Добавьте другие тесты по аналогии

if __name__ == '__main__':
    unittest.main()