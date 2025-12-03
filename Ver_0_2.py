import os

from PyQt5 import QtCore, QtGui, QtWidgets
import sys, heapq

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor, QColor, QTransform
from BaseElement import *


class ConnectionPoint:
    def __init__(self, parent, kind):
        self.parent:DraggableObject = parent
        self.kind = kind  # 'in' или 'out'
        self.x = 0
        self.y = 0
        self.i = 0
        self.pipe:QPipe = None

    def get_pos_pipe(self):
        return QtCore.QPoint(self.x, self.y)

    def get_pos(self, i = 0):
        offset = 8
        if type(self.parent) != QPipeIntersection:
            if self.kind == 'in':
                x = self.parent.position.x() - offset
                y = self.parent.position.y() + self.parent.size // 2
            else:  # 'out'
                x = self.parent.position.x() + self.parent.size + offset
                y = self.parent.position.y() + self.parent.size // 2
        else:
            x = 0
            y = 0
            if self.parent.mode == 'split':
                if self.kind == 'in':
                    x = self.parent.position.x() - offset
                    y = self.parent.position.y() + self.parent.size // 2
                elif self.kind == 'out' and self.i ==1:  # 'out'
                    x = self.parent.position.x() + self.parent.size + offset
                    y = self.parent.position.y() + self.parent.size // 2 - 20
                elif self.kind == 'out' and self.i == 2:
                    x = self.parent.position.x() + self.parent.size + offset
                    y = self.parent.position.y() + self.parent.size // 2 + 20
            elif self.parent.mode == 'merge':
                if self.kind == 'in' and self.i == 1:
                    x = self.parent.position.x() - offset
                    y = self.parent.position.y() + self.parent.size // 2 - 20
                elif self.kind == 'in' and self.i == 2:
                    x = self.parent.position.x() - offset
                    y = self.parent.position.y() + self.parent.size // 2 + 20
                elif self.kind == 'out':  # 'out'
                    x = self.parent.position.x() + self.parent.size + offset
                    y = self.parent.position.y() + self.parent.size // 2

        self.x = x
        self.y = y
        return QtCore.QPoint(x, y)

    def paint(self, painter, i = 0):
        if type(self.parent) == QPipeIntersection:
            pos = self.get_pos(i=i)
        else:
            pos = self.get_pos()
        radius = 6
        color = QtGui.QColor(50, 150, 255) if self.kind == 'in' else QtGui.QColor(255, 180, 50)
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.black)
        painter.drawEllipse(pos, radius, radius)

    def contains(self, pos):
        if type(self.parent) != QPipeIntersection:
            point = self.get_pos()
            radius = 8  # чуть больше радиуса рисования
            return (point - pos).manhattanLength() <= radius
        else:
            point = QtCore.QPoint(self.x, self.y)
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
    @staticmethod
    def is_near(point, cursor_pos, threshold=10):
        dx = point.x() - cursor_pos.x()
        dy = point.y() - cursor_pos.y()
        distance_squared = dx*dx + dy*dy
        return distance_squared <= threshold*threshold

    @staticmethod
    def ellipse_bounding_rect(center_x, center_y, rx, ry):
        """
        Возвращает параметры прямоугольника, в который вписан эллипс
        с центром (center_x, center_y) и радиусами rx, ry.
        """
        left = center_x - rx
        top = center_y - ry
        width = 2 * rx
        height = 2 * ry
        return (left, top, width, height)

    def __init__(self, x, y, tag="Element", size=40, color=QtGui.QColor(100, 200, 150), image_path=None, logic_element=None, process_scheme=None):
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
        if type(self) != QPipe:
            rect = self.get_rect()
            return rect.contains(point)
        else:
            return

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
            self.position.x() + (self.size - text_width) // 2,
            self.position.y() + self.size,
            text_width,
            20
        )
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, self.tag)
        if hasattr(self, "in_point") and self.in_point:
            self.in_point.paint(painter)
        if hasattr(self, "out_point") and self.out_point:
            self.out_point.paint(painter)

    def delete(self):
        result = []
        if self.in_point.pipe != None:
            result.append(self.in_point.pipe)
            self.in_point.pipe.delete()
        if self.out_point.pipe != None:
            result.append(self.out_point.pipe)
            self.out_point.pipe.delete()
        return result



class QPump(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Насос'):
        image_path = QtGui.QPixmap('icon/MOT_2.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)

class QMov(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Задвижка'):
        image_path = QtGui.QPixmap('icon/MOV_2.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)

class QBoiler(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, tag='Котел'):
        self.size = 100
        image_path = QtGui.QPixmap('icon/BOILER.png')
        super().__init__(x, y, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)
        self.working = False

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

class QPipe(DraggableObject):
    @staticmethod
    def line_intersects_rect(p1, p2, rect):
        bounding = QPipe.safe_bounding_rect(p1, p2)
        if bounding.width() == 0 and bounding.height() == 0:
            return False
        return rect.intersects(bounding)

    @staticmethod
    def safe_bounding_rect(p1, p2):
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        if width == 0:
            width = 1
        if height == 0:
            height = 1
        return QtCore.QRect(left, top, width, height)

    @staticmethod
    def build_orthogonal_path(start, end, obstacles):
        # Построение маршрута по сетке, обходя препятствия
        # Для простоты — реализуем "зигзаг" с проверкой пересечений
        path = [start]
        # Первый сегмент — по X
        mid_x = QtCore.QPoint(end.x(), start.y())
        if QPipe.line_intersects_any(start, mid_x, obstacles):
            # добавляем "обход" по Y
            y_offset = -50
            mid_point = QtCore.QPoint(start.x(), start.y() + y_offset)
            path.append(mid_point)
            path.append(QtCore.QPoint(end.x(), mid_point.y()))
        else:
            path.append(mid_x)
        path.append(end)
        return path

    @staticmethod
    def line_intersects_any(start, end, obstacles):
        bounding = QPipe.safe_bounding_rect(start, end)
        for rect in obstacles:
            if rect.intersects(bounding):
                return True
        return False

    def __init__(self, start_point:ConnectionPoint, end_point:ConnectionPoint, start_logic, end_logic, logic_element=None,
                 process_scheme=None, parent_widget=None):
        super().__init__(0, 0, tag='', size=0, color=QtGui.QColor(0,0,0,0))
        # self.start_point = start_point
        # self.end_point = end_point
        self.sensors = []
        self.in_point = start_point
        self.in_point.pipe = self
        self.out_point = end_point
        self.out_point.pipe = self
        self.logic_element = logic_element
        self.parent_widget:WidgetWithObjects = parent_widget
        self.path_points:list[QPoint] = []
        if self.logic_element and process_scheme:
            process_scheme.add_element(self.logic_element)
        if start_logic and end_logic:
            self.logic_element.add_in_element(start_logic)
            self.logic_element.add_out_element(end_logic)
            start_logic.add_out_element(self.logic_element)
            end_logic.add_in_element(self.logic_element)

    def paint(self, painter):
        p1 = self.in_point.get_pos()
        p2 = self.out_point.get_pos()

        # Собираем препятствия
        obstacles = []
        parent_widget = self.parent_widget
        if parent_widget:
            for obj in parent_widget.objects:
                if obj is self:
                    continue
                rect = getattr(obj, "get_rect", lambda: None)()
                if isinstance(rect, QtCore.QRect) and rect.width() > 0 and rect.height() > 0:
                    obstacles.append(rect)

        # Построение маршрута обхода препятствий
        path_points = self.build_path(p1, p2, obstacles)
        self.path_points = path_points
        # Рисуем линии между точками маршрута
        pen = QtGui.QPen(QtCore.Qt.darkGreen, 10)
        painter.setPen(pen)
        for i in range(len(path_points) - 1):
            painter.drawLine(path_points[i], path_points[i+1])

    def build_path(self, start, end, obstacles):
        grid_size = 20  # размер ячейки
        # Создаем сетку по размерам области
        min_x = 0
        max_x = self.parent_widget.width()
        min_y = 0
        max_y = self.parent_widget.height()

        grid_width = int((max_x - min_x) / grid_size) + 1
        grid_height = int((max_y - min_y) / grid_size) + 1

        # Создаем массив ячеек
        grid = [[0 for _ in range(grid_width)] for _ in range(grid_height)]

        # Помечаем ячейки, занятые препятствиями
        for rect in obstacles:
            if rect != self.in_point.parent and rect != self.out_point.parent:
                # Определяем диапазон ячеек, покрывающих препятствие
                start_x_idx = int((rect.left() - min_x) / grid_size)
                end_x_idx = int((rect.right() - min_x) / grid_size)
                start_y_idx = int((rect.top() - min_y) / grid_size)
                end_y_idx = int((rect.bottom() - min_y) / grid_size)
                for y in range(start_y_idx, end_y_idx + 1):
                    for x in range(start_x_idx, end_x_idx + 1):
                        if 0 <= y < grid_height and 0 <= x < grid_width:
                            grid[y][x] = 1  # 1 — препятствие

        # Запускаем A* или BFS
        path_cells = self.a_star(grid, start, end, min_x, min_y, grid_size)
        # Преобразуем ячейки в точки
        path_points = [self.cell_to_point(x, y, min_x, min_y, grid_size) for x, y in path_cells]
        path_points.insert(1, path_points[0])
        path_points[0] = QtCore.QPoint(path_points[0].x() -10, path_points[0].y())
        path_points[-1] = QtCore.QPoint(path_points[-1].x() -10, path_points[-1].y())
        return path_points

    def cell_to_point(self, x_idx, y_idx, min_x, min_y, grid_size):
        return QtCore.QPoint(
            min_x + x_idx * grid_size + grid_size,
            min_y + y_idx * grid_size + grid_size - 20
        )

    def a_star(self, grid, start_point, end_point, min_x, min_y, grid_size):
        """
        grid: 2D список, где 0 — проходимо, 1 — препятствие
        start_point, end_point: QPoint — начальная и конечная точки
        min_x, min_y: минимальные координаты области
        grid_size: размер ячейки
        """
        start_x = int((start_point.x() - min_x) / grid_size)
        start_y = int((start_point.y() - min_y) / grid_size)
        end_x = int((end_point.x() - min_x) / grid_size)
        end_y = int((end_point.y() - min_y) / grid_size)

        open_set = []
        heapq.heappush(open_set, (0, (start_x, start_y)))
        came_from = {}
        g_score = { (start_x, start_y): 0 }
        f_score = { (start_x, start_y): self.heuristic(start_x, start_y, end_x, end_y) }

        while open_set:
            current_f, current = heapq.heappop(open_set)
            if current == (end_x, end_y):
                return self.reconstruct_path(came_from, current)

            neighbors = self.get_neighbors(grid, current)
            for neighbor in neighbors:
                tentative_g = g_score[current] + 1  # стоимость перехода (можно усложнить)
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self.heuristic(neighbor[0], neighbor[1], end_x, end_y)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        return []  # путь не найден

    def heuristic(self, x1, y1, x2, y2):
        # Манхэттенская дистанция
        return abs(x1 - x2) + abs(y1 - y2)

    def get_neighbors(self, grid, node):
        x, y = node
        neighbors = []
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
                if grid[ny][nx] == 0:  # проходимо
                    neighbors.append((nx, ny))
        return neighbors

    def reconstruct_path(self, came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def get_rect(self):
        return self.path_points

    def delete(self):
        if self.in_point.parent != None:
            self.in_point.pipe = None
            self.in_point = None
        if self.out_point != None:
            self.out_point.pipe = None
            self.out_point = None


class QSensor:
    pass

class QPipeIntersection(DraggableObject):
    #def __init__(self, mode='split', label=''):
    def __init__(self, x, y, logic_element, process_scheme, tag='',
                 mode='split'):
        super().__init__(x, y, tag=tag, size=40, logic_element=logic_element, process_scheme=process_scheme)
        #'icon/PipeIntersection.png'
        if mode == 'split':
            self.image = QtGui.QPixmap('icon/PipeIntersection.png')
        else:
            image = QtGui.QPixmap('icon/PipeIntersection.png')
            transform = QTransform().rotate(180)
            self.image = image.transformed(transform)
        self.mode = mode
        self.label = ""
        # Создаем логический элемент.
        # Создаем точки соединения
        self.create_points()

    def create_points(self):
        # Очистить старые точки
        self.in_point = []
        self.out_point = []

        if self.mode == 'split':
            # один вход слева
            in_pt = ConnectionPoint(self, 'in')
            #in_pt.get_pos = lambda: QtCore.QPoint(-self.size/2, 0)
            in_pt.get_pos(True)
            self.in_point.append(in_pt)
            # несколько выходов справа
            for x in range(2):  # например, 2 выхода
                out_pt = ConnectionPoint(self, 'out')
                #out_pt.get_pos = lambda i=x : QtCore.QPoint(self.size//2, (i - 0.5) * 20)
                out_pt.get_pos(True)
                self.out_point.append(out_pt)

        elif self.mode == 'merge':
            # несколько входов слева
            for x in range(2):
                in_pt = ConnectionPoint(self, 'in')
                #in_pt.get_pos = lambda i=x : QtCore.QPoint(-self.size//2, (i - 0.5) * 20)
                in_pt.get_pos(True)
                self.in_point.append(in_pt)
            # один выход справа
            out_pt = ConnectionPoint(self, 'out')
            #out_pt.get_pos = lambda: QtCore.QPoint(self.size/2, 0)
            out_pt.get_pos(True)
            self.out_point.append(out_pt)

    def boundingRect(self):
        return QtCore.QRectF(-self.size/2, -self.size/2, self.size, self.size)

    def paint(self, painter, option=None, widget=None):
        # Рисуем символ (например, круг)
        painter.setBrush(QtGui.QColor(150, 150, 150))
        painter.setPen(QtCore.Qt.black)
        # Подпись
        painter.setPen(QtCore.Qt.black)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        # Рисуем точки соединения
        i = 0
        for pt in self.in_point:
            i += 1
            pt.i = i
            pt.paint(painter, i=i)
        i = 0
        for pt in self.out_point:
            i += 1
            pt.i = i
            pt.paint(painter, i=i)

# --- Класс для сетки и привязки ---
class WidgetWithObjects(QtWidgets.QWidget):
    def __init__(self, controller, process_scheme:ProcessScheme, map=None, parent=None):
        super().__init__(parent)
        self.process_scheme = process_scheme
        self.controller = controller
        self.setGeometry(0, 0, 1300, 800)
        self.objects:list[DraggableObject] = []
        self.selected_object = None
        self.offset = QtCore.QPoint()
        self.proximity_threshold = 0
        self.grid_size = 20  # Размер клетки сетки
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.pipe_start_obj = None
        self.pipe_end_obj = None
        self.pipe_start_point = None
        self.pipe_end_point = None
        self.scene_offset = QtCore.QPoint(0, 0)  # смещение сцены
        self.dragging = False
        self.drag_start_pos = None
        self.offset_at_drag_start = QtCore.QPoint(0, 0)
        self.scene_width = 2000
        self.scene_height = 2000
        self.controller.element_changed.connect(self.set_selected_element)
        self.map:MapWidget = map

        # Скролл
        # self.setViewportMargins(0, 0, 0, 0)
        # self.horizontalScrollBar().setRange(0, self.scene_width - self.viewport().width())
        # self.verticalScrollBar().setRange(0, self.scene_height - self.viewport().height())
        # self.horizontalScrollBar().valueChanged.connect(self.update)
        # self.verticalScrollBar().valueChanged.connect(self.update)


    # def resizeEvent(self, event):
    #     self.horizontalScrollBar().setPageStep(self.viewport().width())
    #     self.verticalScrollBar().setPageStep(self.viewport().height())
    #     self.horizontalScrollBar().setRange(0, self.scene_width - self.viewport().width())
    #     self.verticalScrollBar().setRange(0, self.scene_height - self.viewport().height())
    #     super().resizeEvent(event)

    def pos_scene(self, event):
        scene_pos = event.pos() + QtCore.QPoint(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        return scene_pos

    def clamp_scene_offset(self, offset):
        # Размеры рабочей области (например, 2000x2000)
        scene_width = 2000
        scene_height = 2000

        # Размер видимой области (размер виджета)
        view_width = self.width()
        view_height = self.height()

        # Максимальные смещения (чтобы поле не ушло за границы)
        min_x = min(0, view_width - scene_width)
        min_y = min(0, view_height - scene_height)
        max_x = 0
        max_y = 0

        x = max(min_x, min(offset.x(), max_x))
        y = max(min_y, min(offset.y(), max_y))
        return QtCore.QPoint(x, y)

    def set_selected_element(self, name):
        self.selected_element = name
        if name:
            self.setCursor(QtCore.Qt.CrossCursor)
        else:
            self.unsetCursor()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.save()
        painter.translate(self.scene_offset)
        self.draw_grid(painter)
        # Смещение сцены по скроллбару
        # offset = QtCore.QPoint(-self.horizontalScrollBar().value(), -self.verticalScrollBar().value())
        # painter.save()
        # painter.translate(offset)
        self.draw_grid(painter)
        for obj in self.objects:
            obj.paint(painter)
            painter.drawPixmap(obj.position.x(), obj.position.y(), obj.size, obj.size, obj.image)
        painter.restore()
        self.map.update()

            # obj.paint(painter)

    def draw_grid(self, painter):
        pen = QtGui.QPen(QColor(200, 200, 200))
        painter.setPen(pen)
        # учтите смещение при рисовании линий
        for x in range(-self.scene_offset.x() % self.grid_size, self.width(), self.grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(-self.scene_offset.y() % self.grid_size, self.height(), self.grid_size):
            painter.drawLine(0, y, self.width(), y)

    def snap_to_grid(self, pos):
        x = (pos.x() // self.grid_size) * self.grid_size
        y = (pos.y() // self.grid_size) * self.grid_size
        return QtCore.QPoint(x, y)

    def is_cell_free(self, rect, exclude_obj=None):
        for obj in self.objects:
            if type(obj) != QPipe:
                if obj is exclude_obj:
                    continue
                if rect.intersects(obj.get_rect()):
                    return False
        return True

    def get_connection_point_at(self, pos):
        result = []
        for obj in reversed(self.objects):
            if type(obj.in_point) == list:
                for x in obj.in_point:
                    result.append(x)
            else:
                result.append(obj.in_point)
            if type(obj.out_point) == list:
                for x in obj.out_point:
                    result.append(x)
            else:
                result.append(obj.out_point)
            for point in result:
                if point.contains(pos):
                    return point, obj
        return None, None

    def mousePressEvent(self, event):
        self.setFocus()
        if hasattr(self, 'selected_element') and self.selected_element:
            if event.button() == QtCore.Qt.LeftButton:
                pos = self.pos_scene(event)
                # Создаём объект по выбранному элементу
                if self.selected_element == "QPump":
                    logic_obj = PumpElement()
                    new_obj = QPump(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QMov":
                    logic_obj = MovElement()
                    new_obj = QMov(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QBoiler":
                    logic_obj = BoilerElement()
                    new_obj = QBoiler(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QPipeIntersection|Split":
                    logic_obj = PipeIntersectionElement(mode='split')
                    new_obj = QPipeIntersection(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QPipeIntersection|Merge":
                    logic_obj = PipeIntersectionElement(mode='merge')
                    new_obj = QPipeIntersection(pos.x(), pos.y(), logic_element=logic_obj, process_scheme=self.process_scheme, mode='merge')
                elif self.selected_element == "QPipe":
                    point, obj = self.get_connection_point_at((event.pos() - self.scene_offset))
                    if point and obj:
                        if not self.pipe_start_obj:
                            if point.kind == 'out':
                                self.pipe_start_obj = obj
                                self.pipe_start_point = point
                        else:
                            if point.kind == 'in' and obj != self.pipe_start_obj:
                                self.pipe_end_obj = obj
                                self.pipe_end_point = point
                                # Создаём линию
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
                    new_obj = DraggableObject(pos.x(), pos.y())
                # Привязка к сетке
                new_obj.position = self.snap_to_grid(new_obj.position)
                self.objects.append(new_obj)
                self.selected_element = None
                self.controller.set_element(None)
                self.unsetCursor()
                self.update()
        elif event.button() == QtCore.Qt.MiddleButton:
            self.dragging = True
            self.drag_start_pos = event.pos()
            self.offset_at_drag_start = self.scene_offset
        else:
            # Перетаскивание объектов
            scene_pos = self.pos_scene(event)
            for obj in reversed(self.objects):
                if obj.contains(scene_pos):
                    self.selected_object = obj
                    obj.dragging = True
                    self.offset = scene_pos - obj.position
                    self.update()
                    break


    def mouseMoveEvent(self, event):
        if self.selected_object and self.selected_object.dragging:
            # Перетаскивание объекта
            scene_pos = self.pos_scene(event)
            new_pos = scene_pos - self.offset
            new_pos = self.snap_to_grid(new_pos)
            self.selected_object.position = new_pos
            self.update()
        if self.dragging:
            delta = self.pos_scene(event)
            self.horizontalScrollBar().setValue(self.start_scroll_x - delta.x())
            self.verticalScrollBar().setValue(self.start_scroll_y - delta.y())

    def get_obj_rect_at(self, pos, obj):
        rect = QtCore.QRect(pos.x(), pos.y(), obj.size, obj.size)
        return rect

    def mouseReleaseEvent(self, event):
        if self.selected_object:
            self.selected_object.dragging = False
            self.selected_object = None
        # if event.button() != QtCore.Qt.MiddleButton:
        if self.dragging:
            self.dragging = False

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.selected_element = None
            self.setCursor(QtCore.Qt.ArrowCursor)
        elif event.key() == QtCore.Qt.Key_A:
            self.add_object(event)
        elif event.key() == QtCore.Qt.Key_D:
            self.remove_selected_object()
        elif event.key() == QtCore.Qt.Key_F:
            for x in self.objects:
                print(f'Element ---------------------{x}')
                x:DraggableObject
                print(f'IN ---{x.in_point}')
                print(f' in_element {x.in_point.pipe}')
                print(f'OUT ---{x.out_point}')
                print(f' out_element {x.out_point.pipe}')
                print('-------------------------------------------------------------')
                # if type(x) == QPipe:
                #     print(f'Element ---------------------{x}')
                #     x:DraggableObject
                #     print(f'IN ---{x.in_point}')
                #     print(f' in_element {x.in_point.parent}')
                #
                #     print(f'OUT ---{x.out_point}')
                #     print(f' out_element {x.out_point.parent}')
                #     print(x.get_rect())



    def add_object(self):
        pos = self.viewport().mapFromGlobal(QCursor.pos())
        # pos = self.snap_to_grid(pos)


        new_obj = DraggableObject(pos.x(), pos.y())
        self.objects.append(new_obj)
        self.viewport().update()

    def remove_selected_object(self):
        pos = self.mapFromGlobal(QCursor.pos()) - self.scene_offset
        for obj in self.objects:
            if type(obj) == QPipe:
                points = obj.get_rect()
                for point in points:
                    if obj.is_near(point, pos, 10):
                        obj.delete()
                        self.objects.remove(obj)
                        break
            else:
                rect = obj.get_rect()
                if rect.contains(pos):
                    rems_obj = obj.delete()
                    self.objects.remove(obj)
                    if rems_obj:
                        for rem_obj in rems_obj:
                            self.objects.remove(rem_obj)
                    break
        self.update()

class MapWidget(QtWidgets.QWidget):
    @staticmethod
    def scene_to_map(scene_point, scene_size, map_size):
        """
        scene_point: QPoint или (x, y) — координаты на сцене
        scene_size: (scene_width, scene_height)
        map_size: (map_width, map_height)
        """
        scale_x = map_size[0] / scene_size[0]
        scale_y = map_size[1] / scene_size[1]
        map_x = scene_point.x() * scale_x
        map_y = scene_point.y() * scale_y
        return QtCore.QPointF(map_x, map_y)

    def __init__(self, redactor, parent=None):
        super().__init__(parent)
        self.redactor = redactor  # ссылка на основной виджет сцены
        self.setMinimumSize(200, 200)  # можно изменить под ваши нужды

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Размеры мини-карты
        map_width = self.width()
        map_height = self.height()

        # Размеры всей сцены
        scene_width = self.redactor.scene_width
        scene_height = self.redactor.scene_height

        # Размер видимой области (размер виджета)
        view_width = self.redactor.width()
        view_height = self.redactor.height()

        # Смещение сцены (если есть)
        offset = self.redactor.scene_offset

        # Масштаб мини-карты
        scale_x = map_width / scene_width
        scale_y = map_height / scene_height

        # --- Рисуем всю сцену (большой прямоугольник) ---
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 2))
        painter.setBrush(QtGui.QColor(220, 220, 220))
        painter.drawRect(0, 0, map_width, map_height)

        # --- Рисуем видимую область (маленький прямоугольник) ---
        # Координаты видимой области на мини-карте
        point_f= self.scene_to_map(QtCore.QPoint(-offset.x(), -offset.y()),
                                           (scene_width, scene_height),
                                           (map_width, map_height))
        view_x = point_f.x()
        view_y = point_f.y()
        view_w = int(view_width * scale_x)
        view_h = int(view_height * scale_y)
        painter.drawRect(int(view_x), int(view_y), view_w, view_h)

        # painter.setPen(QtGui.QPen(QtCore.Qt.red, 2))
        # painter.setBrush(QtCore.Qt.NoBrush)
        # painter.drawRect(view_x, view_y, view_w, view_h)
        # Пример: рисуем все объекты как точки на миникарте
        if len(self.redactor.objects) != 0:
            for obj in self.redactor.objects:
                if type(obj) != QPipe:
                    map_pos = self.scene_to_map(obj.position,
                                                (self.redactor.scene_width, self.redactor.scene_height),
                                                (self.width(), self.height()))
                    painter.setPen(QtCore.Qt.blue)
                    painter.setBrush(QtCore.Qt.blue)
                    painter.drawEllipse(map_pos, 3, 3)

# --- Основная часть ---
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.process_scheme = ProcessScheme()
        self.setWindowTitle("Редактор с сеткой")
        self.resize(1600, 900)
        self.controller = ElementController()
        self.redactor = WidgetWithObjects(self.controller, self.process_scheme)
        self.setCentralWidget(self.redactor)

        self.mapWidget = QtWidgets.QDockWidget('Карта', self)
        self.mapWidget.setMinimumSize(QtCore.QSize(220, 220))
        self.mapWidget.setStyleSheet("background-color: rgb(177, 177, 177);")
        self.mapWidget.setAllowedAreas(QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
        self.mapWidgetContents = MapWidget(self.redactor)

        self.mapWidget.setWidget(self.mapWidgetContents)
        self.redactor.map = self.mapWidgetContents


        # Настройка элементов для выбора
        self.dockWidget = QtWidgets.QDockWidget('Элементы', self)
        self.dockWidget.setMinimumSize(QtCore.QSize(220, 300))
        self.dockWidget.setStyleSheet("background-color: rgb(177, 177, 177);")
        self.dockWidget.setAllowedAreas(QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
        self.dockWidgetContents = QtWidgets.QListWidget()
        self.dockWidgetContents.setIconSize(QtCore.QSize(48, 48))
        items = [
            ("QPump", "icon/MOT_2.png"),
            ("QMov", "icon/MOV_2.png"),
            ("QBoiler", "icon/BOILER.png"),
            ("QPipe", "icon/PIPE.png"),
            ("QPipeIntersection|Split", "icon/PipeIntersection.png"),
            ("QPipeIntersection|Merge", "icon/PipeIntersection_merge.png")
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

# --- Запуск ---
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


