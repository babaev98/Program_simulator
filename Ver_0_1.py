import os

from PyQt5 import QtCore, QtGui, QtWidgets
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor, QColor
from BaseElement import *


class ConnectionPoint:
    def __init__(self, parent, kind):
        self.parent = parent
        self.kind = kind  # 'in' или 'out'
        self.x = 0
        self.y = 0

    def get_pos(self):
        offset = 8
        if self.kind == 'in':
            x = self.parent.position.x() - offset
            y = self.parent.position.y() + self.parent.size // 2
        else:  # 'out'
            x = self.parent.position.x() + self.parent.size + offset
            y = self.parent.position.y() + self.parent.size // 2
        self.x = x
        self.y = y
        return QtCore.QPoint(x, y)

    def paint(self, painter):
        pos = self.get_pos()
        radius = 6
        color = QtGui.QColor(50, 150, 255) if self.kind == 'in' else QtGui.QColor(255, 180, 50)
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.black)
        painter.drawEllipse(pos, radius, radius)

    def contains(self, pos):
        point = self.get_pos()
        radius = 8  # чуть больше радиуса рисования
        return (point - pos).manhattanLength() <= radius


class ElementController(QtCore.QObject):
    element_changed = QtCore.pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._selected_element = None
    def set_element(self, name):
        self._selected_element = name
        self.element_changed.emit(name)
    def get_element(self):
        return self._selected_element


class DraggableObject:
    def __init__(self, x, y, tag="Element", size=50, color=QtGui.QColor(100, 200, 150), image_path=None, logic_element=None, process_scheme=None):
        self.position = QtCore.QPoint(x, y)
        self.size = size  # Квадрат 50x50
        self.color = color
        self.dragging = False
        self.image = QtGui.QPixmap('icon/Default.png') if image_path is None else image_path
        self.tag = tag  # Подпись под иконкой
        self.logic_element = logic_element
        if self.logic_element and process_scheme:
            process_scheme.add_element(self.logic_element)
        self.in_point = ConnectionPoint(self, 'in')
        self.out_point = ConnectionPoint(self, 'out')

    def contains(self, point):
        rect = self.get_rect()
        return rect.contains(point)

    def get_rect(self):
        return QtCore.QRect(self.position.x(), self.position.y(), self.size, self.size + 20)  # +20 для подписи

    def get_connection_point(self, kind):
        return self.in_point if kind == 'in' else self.out_point

    def paint(self, painter):
        # Рисуем квадрат
        painter.setBrush(self.color)
        painter.drawRect(self.position.x(), self.position.y(), self.size, self.size)
        # Рисуем иконку
        if self.image:
            icon_rect = QtCore.QRect(self.position.x(), self.position.y(), self.size, self.size)
            painter.drawPixmap(icon_rect, self.image.scaled(50, 50, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        # Рисуем подпись по центру под иконкой
        painter.setPen(QtCore.Qt.black)
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        text_width = 80
        text_rect = QtCore.QRect(
            self.position.x() + (self.size - text_width) // 2,  # смещаем влево, чтобы центр совпал с иконкой
            self.position.y() + self.size,
            text_width,
            20
        )
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, self.tag)
        if hasattr(self, "in_point") and self.in_point:
            self.in_point.paint(painter)
        if hasattr(self, "out_point") and self.out_point:
            self.out_point.paint(painter)

class QPump(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Задвижка'):
        image_path = QtGui.QPixmap('icon/MOT.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)


class QMov(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Задвижка'):
        image_path = QtGui.QPixmap('icon/MOV.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)


class QBoiler(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Котел'):
        self.size = 100  # В два раза больше
        image_path = QtGui.QPixmap('icon/BOILER.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)
        self.working = False  # Индикатор работы

    def set_working(self, state: bool):
        self.working = state

    def paint(self, painter):
        self.draw_background(painter)
        self.draw_icon(painter)
        self.draw_label(painter)
        self.draw_indicator(painter)

    def draw_background(self, painter):
        painter.setBrush(self.color)
        painter.drawRect(self.position.x(), self.position.y(), self.size, self.size)

    def draw_icon(self, painter):
        if self.image:
            icon_rect = QtCore.QRect(self.position.x(), self.position.y(), self.size, self.size)
            painter.drawPixmap(icon_rect, self.image.scaled(self.size, self.size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    def draw_label(self, painter):
        painter.setPen(QtCore.Qt.black)
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        text_width = 120
        text_rect = QtCore.QRect(
            self.position.x() + (self.size - text_width) // 2,
            self.position.y() + self.size,
            text_width,
            24
        )
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, self.tag)

    def draw_indicator(self, painter):
        indicator_radius = 12
        indicator_color = QtGui.QColor(0, 200, 0) if self.working else QtGui.QColor(200, 0, 0)
        painter.setBrush(indicator_color)
        painter.setPen(QtCore.Qt.NoPen)
        indicator_center = QtCore.QPoint(self.position.x() + self.size - indicator_radius, self.position.y() + indicator_radius)
        painter.drawEllipse(indicator_center, indicator_radius, indicator_radius)


# class QPipe(DraggableObject):
#     def __init__(self, x, y, logic_element, process_scheme, tag=''):
#         image_path = QtGui.QPixmap('icon/PIPE.png')
#         super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)
class QPipe(DraggableObject):
    @staticmethod
    # def line_intersects_rect(p1, p2, rect):
    #     # Проверка: пересекает ли отрезок p1-p2 прямоугольник rect
    #     line = QtCore.QLine(p1, p2)
    #     return rect.intersects(line.boundingRect())
    def line_intersects_rect(p1, p2, rect):
        bounding = QPipe.safe_bounding_rect(p1, p2)
        if bounding.width() == 0 and bounding.height() == 0:
            return False  # Не пересекает, потому что это точка
        return rect.intersects(bounding)
    @staticmethod
    def safe_bounding_rect(p1, p2):
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        # Если линия горизонтальная или вертикальная, делаем высоту/ширину хотя бы 1
        if width == 0:
            width = 1
        if height == 0:
            height = 1
        return QtCore.QRect(left, top, width, height)
    @staticmethod
    def find_orthogonal_path(start, end, obstacles, pipes):
        """
        Строит ортогональный маршрут от start до end, обходя obstacles (QRect).
        pipes — список QPipe для перепрыгивания.
        Возвращает список QPoint.
        """
        path = [start]
        current = start
        # Простейший вариант: сначала по X, потом по Y
        intermediate = QtCore.QPoint(end.x(), start.y())

        # Проверяем пересечение с препятствиями
        for rect in obstacles:
            if QPipe.line_intersects_rect(current, intermediate, rect):
                # Обходим obstacle: добавляем точку выше
                y = rect.top() - 20
                path.append(QtCore.QPoint(current.x(), y))
                path.append(QtCore.QPoint(end.x(), y))
                break
        path.append(intermediate)
        path.append(end)
        return path
    @staticmethod
    def build_orthogonal_path(start, end):
        points = [start]
        mid_point = QtCore.QPoint(end.x(), start.y())
        points.append(mid_point)
        points.append(end)
        return points

    def __init__(self, start_point, end_point, start_logic, end_logic, logic_element=None,
                 process_scheme=None, parent_widget = None):
        super().__init__(0, 0, tag='', size=0, color=QtGui.QColor(0,0,0,0))
        self.start_point = start_point  # ConnectionPoint (out)
        self.end_point = end_point      # ConnectionPoint (in)
        self.logic_element = logic_element
        self.parent_widget = parent_widget
        if self.logic_element and process_scheme:
            process_scheme.add_element(self.logic_element)
        # Логическая связь: труба между двумя логическими элементами
        if start_logic and end_logic:
            # Труба между start_logic и end_logic
            self.logic_element.add_in_element(start_logic)
            self.logic_element.add_out_element(end_logic)
            start_logic.add_out_element(self.logic_element)
            end_logic.add_in_element(self.logic_element)

    def paint(self, painter):
        painter.setBrush(QtCore.Qt.NoBrush)
        pen = QtGui.QPen(QtCore.Qt.darkBlue, 8)
        painter.setPen(pen)
        p1 = self.start_point.get_pos()
        p2 = self.end_point.get_pos()

        # Собираем препятствия
        obstacles = []
        parent_widget = self.parent_widget
        connect_obj = getattr(self, 'connect_obj', None)  # объект, который соединяет линии (если есть)

        if parent_widget:
            for obj in parent_widget.objects:
                # исключаем текущий QPipe
                if obj is self:
                    continue
                # исключаем объект, который соединяет линии
                if connect_obj and obj is connect_obj:
                    continue
                # добавляем все остальные объекты
                rect = getattr(obj, "get_rect", lambda: None)()
                if isinstance(rect, QtCore.QRect) and rect.width() > 0 and rect.height() > 0:
                    obstacles.append(rect)

        # Построение "зигзага" по X и Y
        def build_orthogonal_path(start, end):
            points = [start]
            mid_point = QtCore.QPoint(end.x(), start.y())
            points.append(mid_point)
            points.append(end)
            return points

        # Создаём маршрут
        path_points = build_orthogonal_path(p1, p2)

        # Рисуем линию по маршруту
        path = QtGui.QPainterPath()
        path.moveTo(path_points[0])
        for pt in path_points[1:]:
            path.lineTo(pt)
        painter.drawPath(path)

    # Для отладки — можно добавить проверку пересечений
    # (опционально)
    # for i in range(len(path_points) - 1):
    #     print("Line segment:", path_points[i], path_points[i+1])
    # def paint(self, painter):
    #     painter.setBrush(QtCore.Qt.NoBrush)
    #     pen = QtGui.QPen(QtCore.Qt.darkBlue, 8)
    #     painter.setPen(pen)
    #     p1 = self.start_point.get_pos()
    #     p2 = self.end_point.get_pos()
    #
    #     # Собираем препятствия (все объекты, кроме self и других QPipe)
    #     obstacles = []
    #     pipes = []
    #     parent_widget = self.parent_widget  # WidgetWithObjects
    #     if parent_widget:
    #         for obj in parent_widget.objects:
    #             if obj is self or isinstance(obj, QPipe):
    #                 if obj is not self:
    #                     pipes.append(obj)
    #                 continue
    #             # --- ФИЛЬТРАЦИЯ ---
    #             rect = getattr(obj, "get_rect", lambda: None)()
    #             if isinstance(rect, QtCore.QRect) and rect.width() > 0 and rect.height() > 0:
    #                 obstacles.append(rect)
    #     else:
    #         painter.drawLine(p1, p2)
    #         return
    #
    #     # Строим маршрут
    #
    #     path_points = self.find_orthogonal_path(p1, p2, obstacles, pipes)
    #     print(obstacles, 'asd')
    #     # Рисуем маршрут
    #     path = QtGui.QPainterPath()
    #     path.moveTo(path_points[0])
    #     for pt in path_points[1:]:
    #         path.lineTo(pt)
    #     painter.drawPath(path)
    #
    #     # Перепрыгивание труб (очень упрощённо: рисуем дугу на пересечении)
    #     for pipe in pipes:
    #         # Для каждого сегмента маршрута проверяем пересечение с pipe
    #         for i in range(len(path_points) - 1):
    #             seg_start = path_points[i]
    #             seg_end = path_points[i+1]
    #             pipe_rect = QtCore.QRect(pipe.start_point.get_pos(), pipe.end_point.get_pos()).normalized()
    #             print("Проверка пересечения:", seg_start, seg_end, pipe_rect)
    #             print("Размер pipe_rect:", pipe_rect.width(), pipe_rect.height())
    #             print("line.boundingRect:", QPipe.safe_bounding_rect(seg_start, seg_end))
    #             if self.line_intersects_rect(seg_start, seg_end, pipe_rect):
    #                 # Нарисовать дугу (мостик)
    #                 center = QtCore.QPoint((seg_start.x() + seg_end.x()) // 2, (seg_start.y() + seg_end.y()) // 2)
    #                 arc_rect = QtCore.QRect(center.x() - 10, center.y() - 10, 20, 20)
    #                 painter.setPen(QtGui.QPen(QtCore.Qt.darkBlue, 4))
    #                 painter.drawArc(arc_rect, 0, 180 * 16)  # 180 градусов



class QFlowSource(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Источник'):
        image_path = QtGui.QPixmap('icon/PIPE.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)


class QPipeChange(DraggableObject):
    pass


class QPipeIntersection(DraggableObject):
    pass


class QFilter(DraggableObject):
    pass


class QCapacity(DraggableObject):
    pass


class QThermalFluid(DraggableObject):
    pass


class QValve(DraggableObject):
    pass


class WidgetWithObjects(QtWidgets.QWidget):
    def __init__(self, controller, process_scheme, parent=None):
        super().__init__(parent)
        self.process_scheme = process_scheme  # ссылка на логику
        self.selected_element = None
        self.setGeometry(0, 0, 1300, 800)
        self.objects = []
        self.selected_object = None
        self.offset = QtCore.QPoint()
        self.proximity_threshold = 0
        self.controller = controller
        self.controller.element_changed.connect(self.set_selected_element)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.pipe_start_obj = None
        self.pipe_end_obj = None

    def set_selected_element(self, element_name):
        self.selected_element = element_name
        if element_name:
            self.setCursor(QtCore.Qt.CrossCursor)  # или другой курсор
        else:
            self.unsetCursor()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        for obj in self.objects:
            if obj.image:
                painter.drawPixmap(obj.position.x(), obj.position.y(), obj.size, obj.size, obj.image)
                obj.paint(painter)
            else:
                painter.drawPixmap(obj.position.x(), obj.position.y(), obj.size, obj.size)
                obj.paint(painter)

    def get_connection_point_at(self, pos):
        for obj in reversed(self.objects):
            for point in [obj.in_point, obj.out_point]:
                if point.contains(pos):
                    return point, obj
        return None, None

    def mousePressEvent(self, event):
        self.setFocus()
        if self.selected_element:
            if event.button() == QtCore.Qt.LeftButton:
                pos = event.pos()
                # Импортируйте нужные классы логики

                # Создаём логический и визуальный объект
                if self.selected_element == "QPump":
                    logic_obj = PumpElement()
                    new_obj = QPump(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QMov":
                    logic_obj = MovElement()
                    new_obj = QMov(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QBoiler":
                    logic_obj = BoilerElement()
                    new_obj = QBoiler(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QPipe":
                    point, obj = self.get_connection_point_at(event.pos())
                    if point and obj:
                        if not self.pipe_start_obj:
                            if point.kind == 'out':
                                self.pipe_start_obj = obj
                                self.pipe_start_point = point
                        else:
                            if point.kind == 'in' and obj != self.pipe_start_obj:
                                self.pipe_end_obj = obj
                                self.pipe_end_point = point
                                # Получаем логику
                                start_logic = self.pipe_start_obj.logic_element
                                end_logic = self.pipe_end_obj.logic_element
                                logic_obj = PipeElementElement(length=1.0, diameter=0.1)
                                new_pipe = QPipe(self.pipe_start_point, self.pipe_end_point, start_logic, end_logic,
                                                 logic_element=logic_obj, process_scheme=self.process_scheme,
                                                 parent_widget=self)
                                self.objects.append(new_pipe)
                                self.pipe_start_obj = None
                                self.pipe_end_obj = None
                                self.pipe_start_point = None
                                self.pipe_end_point = None
                                self.selected_element = None
                                self.controller.set_element(None)
                                self.unsetCursor()
                                self.update()
                    return
                else:
                    logic_obj = None
                    new_obj = DraggableObject(pos.x(), pos.y())
                self.objects.append(new_obj)
                self.selected_element = None
                self.controller.set_element(None)
                self.unsetCursor()
                main_window = self.window()
                if hasattr(main_window, "dockWidgetContents"):
                    main_window.dockWidgetContents.clearSelection()
                self.update()
            elif event.button() == QtCore.Qt.RightButton:
                # Отмена выбора элемента
                self.selected_element = None
                self.controller.set_element(None)
                self.unsetCursor()
                main_window = self.window()
                if hasattr(main_window, "dockWidgetContents"):
                    main_window.dockWidgetContents.clearSelection()
        else:
            # Обычное поведение для выделения/перетаскивания объектов
            for obj in reversed(self.objects):
                if obj.contains(event.pos()):
                    self.selected_object = obj
                    obj.dragging = True
                    self.offset = event.pos() - obj.position
                    self.update()
                    break

    def mouseMoveEvent(self, event):
        if self.selected_object and self.selected_object.dragging:
            self.proximity_threshold = self.selected_object.size + 60
            new_pos = event.pos() - self.offset
            for other in self.objects:
                if other != self.selected_object:
                    dist = (new_pos - other.position).manhattanLength()
                    if dist < self.proximity_threshold:
                        return
            self.selected_object.position = new_pos
            self.update()

    def mouseReleaseEvent(self, event):
        if self.selected_object:
            self.selected_object.dragging = False
            self.selected_object = None

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.selected_element = None
            self.controller.set_element(None)
            self.unsetCursor()
            main_window = self.window()
            if hasattr(main_window, "dockWidgetContents"):
                main_window.dockWidgetContents.clearSelection()
        elif event.key() == Qt.Key_A:
            self.add_object()
        elif event.key() == Qt.Key_D:
            self.remove_selected_object()

    def add_object(self):
        local_pos = self.mapFromGlobal(QCursor.pos())
        new_obj = DraggableObject(x=local_pos.x(), y=local_pos.y(), size=50, color=QColor(100, 200, 150))
        self.objects.append(new_obj)
        self.update()

    def remove_selected_object(self):
        local_pos = self.mapFromGlobal(QCursor.pos())
        for obj in self.objects:
            rect = QtCore.QRect(obj.position.x(), obj.position.y(), obj.size, obj.size)
            if rect.contains(local_pos):
                # Удаляем логический элемент из схемы, если есть
                if hasattr(obj, "logic_element") and obj.logic_element and self.process_scheme:
                    index = getattr(obj.logic_element, "index", None)
                    if index is not None:
                        self.process_scheme.remove_element(index)
                # Удаляем визуальный объект
                self.objects.remove(obj)
                break
        self.update()

    def get_object_at(self, pos):
        for obj in reversed(self.objects):
            if obj.contains(pos):
                return obj
        return None

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.process_scheme = ProcessScheme()
        self.setWindowTitle("Редактор с DockWidget")
        self.resize(1600, 900)
        self.controller = ElementController()
        # Центральный виджет
        self.redactor = WidgetWithObjects(self.controller, self.process_scheme)
        self.setCentralWidget(self.redactor)
        # DockWidget
        self.dockWidget = QtWidgets.QDockWidget('Элементы', self)
        self.dockWidget.setMinimumSize(QtCore.QSize(220, 300))
        self.dockWidget.setStyleSheet("background-color: rgb(177, 177, 177);")
        self.dockWidget.setAllowedAreas(QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
        self.dockWidgetContents = QtWidgets.QListWidget()
        self.dockWidgetContents.setIconSize(QtCore.QSize(48, 48))
        items = [
            ("QPump", "icon/MOT.png"),
            ("QMov", "icon/MOV.png"),
            ("QBoiler", "icon/BOILER.png"),
            ("QPipe", "icon/PIPE.png"),
        ]
        for name, icon_path in items:
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(icon_path), name)
            self.dockWidgetContents.addItem(item)
        self.dockWidgetContents.currentItemChanged.connect(self.item_changed)
        self.dockWidget.setWidget(self.dockWidgetContents)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockWidget)

    def item_changed(self, current, previous):
        if current:
            self.controller.set_element(current.text())
            print(f"Selected item: {current.text()}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


