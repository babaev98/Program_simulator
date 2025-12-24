import os
from OpenGL.GL import *
from OpenGL.arrays import vbo
from PyQt5 import QtCore, QtGui, QtWidgets
import sys, heapq
import numpy as np
from PyQt5.QtCore import Qt, QPoint, QRect, QPointF, QTimer, pyqtSlot
from PyQt5.QtGui import QCursor, QColor, QTransform, QIcon
from PyQt5.QtWidgets import QOpenGLWidget, QAction

from BaseElement import *

CONNECTION_MARGIN = 40
MIN_DISTANCE = 60

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
            point = self.get_pos() - self.parent.parent_widget.scene_offset
            radius = 8  # чуть больше радиуса рисования
            return (point - pos).manhattanLength() <= radius
        else:
            point = QtCore.QPoint(self.x, self.y)  - self.parent.parent_widget.scene_offset
            radius = 8  # чуть больше радиуса рисования
            return (point - pos).manhattanLength() <= radius


class ElementController(QtCore.QObject):
    element_changed = QtCore.pyqtSignal(str)
    settings_object_changed = QtCore.pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self._selected_element = None
        self._selected_settings_element = None

    def set_element(self, name:str):
        self._selected_element = name
        self.element_changed.emit(name)

    def set_settings_object(self, obj:object):
        self._selected_settings_element = obj
        self.settings_object_changed.emit(obj)

    def get_element(self):
        return self._selected_element

    def get_settings_object(self):
        return self._selected_settings_element

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

    def __init__(self, x, y, parent_widget, tag="Element", size=40, color=QtGui.QColor(100, 200, 150),  image_path=None, logic_element=None, process_scheme=None):
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
        self.parent_widget:WidgetWithObjects = parent_widget
        self.process_scheme = process_scheme
        self.model = ModelSettings(self)

    def contains(self, point):
        if type(self) != QPipe:
            rect = self.get_rect()
            return rect.contains(point)
        else:
            raise

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

    def get_parameters(self):
        parameters = self.model.get_parameters()
        return parameters

    def delete(self):
        result = []
        if self.in_point.pipe != None:
            result.append(self.in_point.pipe)
            self.in_point.pipe.delete()
        if self.out_point.pipe != None:
            result.append(self.out_point.pipe)
            self.out_point.pipe.delete()
        self.process_scheme.remove_element(self.logic_element.index)
        return result


class QFlowSource(DraggableObject):

    def __init__(self, x, y, logic_element, process_scheme, parent_widget, tag='Первый'):
        image_path = QtGui.QPixmap('icon/FlowSource.png')
        super().__init__(x, y, parent_widget, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)

class QPump(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, parent_widget, tag='Насос'):
        image_path = QtGui.QPixmap('icon/MOT.png')
        super().__init__(x, y, parent_widget, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)

class QMov(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, parent_widget, tag='Задвижка'):
        image_path = QtGui.QPixmap('icon/MOV.png')
        super().__init__(x, y, parent_widget, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)

class QBoiler(DraggableObject):
    def __init__(self, x, y, logic_element, process_scheme, parent_widget, tag='Котел'):
        self.size = 100
        image_path = QtGui.QPixmap('icon/BOILER.png')
        super().__init__(x, y, parent_widget, tag=tag, image_path=image_path, logic_element=logic_element, process_scheme=process_scheme)
        self.working = False

    def set_working(self, state: bool):
        self.working = state

    def paint(self, painter):
        super().paint(painter)
        # self.draw_background(painter)
        # self.draw_icon(painter)
        # self.draw_label(painter)
        # self.draw_indicator(painter)

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


class PipeOpenGLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pipes = []  # список QPipe

    def add_pipe(self, pipe):
        """Добавить трубу в список для отрисовки."""
        if pipe not in self.pipes:
            self.pipes.append(pipe)
        self.update()

    def delete_pipe(self, pipe):
        """Удалить трубу из списка для отрисовки."""
        if pipe in self.pipes:
            self.pipes.remove(pipe)
        self.update()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glColor3f(0.0, 0.6, 0.0)
        glLineWidth(8)
        for pipe in self.pipes:
            if not pipe.path_points:
                continue
            self.draw_pipe_path(pipe.path_points)

    def draw_pipe_path(self, path_points):
        """Рисует линии между точками маршрута трубы."""
        if len(path_points) < 2:
            return
        glBegin(GL_LINE_STRIP)
        for point in path_points:
            glVertex2f(point.x(), point.y())
        glEnd()

    @staticmethod
    def simplify_path(points, epsilon=5):
        """
        Статический метод для упрощения маршрута (например, Ramer–Douglas–Peucker).
        Можно вызывать как PipeOpenGLWidget.simplify_path(points).
        """
        # Здесь должна быть реализация алгоритма упрощения ломаной (RDP)
        # Для примера — просто возвращаем исходный список
        return points


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

    @staticmethod
    def heuristic(x1, y1, x2, y2):
        # Манхэттенская дистанция
        return abs(x1 - x2) + abs(y1 - y2)

    @staticmethod
    def cell_to_point(x_idx, y_idx, min_x, min_y, grid_size):
        return QtCore.QPoint(
            min_x + x_idx * grid_size + grid_size,
            min_y + y_idx * grid_size + grid_size - 20
        )

    @staticmethod
    def get_neighbors(grid, node):
        x, y = node
        neighbors = []
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
                if grid[ny][nx] == 0:  # проходимо
                    neighbors.append((nx, ny))
        return neighbors

    @staticmethod
    def reconstruct_path(came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def __init__(self, start_point:ConnectionPoint, end_point:ConnectionPoint, start_logic, end_logic, logic_element=None,
                 process_scheme=None, parent_widget=None):
        super().__init__(0, 0, parent_widget, tag='', size=0, color=QtGui.QColor(0,0,0,0),process_scheme=process_scheme, logic_element=logic_element)
        # self.start_point = start_point
        # self.end_point = end_point
        self.sensors = []
        self.in_point = start_point
        self.in_point.pipe = self
        self.out_point = end_point
        self.out_point.pipe = self
        # self.path_points:list[QPoint] = []
        self.path_points = []
        if self.logic_element and process_scheme:
            process_scheme.add_element(self.logic_element)
        if start_logic and end_logic:
            self.logic_element.add_in_element(start_logic)
            self.logic_element.add_out_element(end_logic)
            start_logic.add_out_element(self.logic_element)
            end_logic.add_in_element(self.logic_element)
        self.parent_widget.pipes.append(self)


    def get_sensor_attach_point(self, sensor_index, total_sensors):
        # if not self.path_points:
        #     return None
        # if total_sensors == 1:
        #     idx = len(self.path_points) // 2
        # else:
        #     idx = int(sensor_index * (len(self.path_points) - 1) / (total_sensors - 1))
        # return self.path_points[idx]
        if len(self.sensors) == 1:
            point = self.path_points[int(len(self.path_points)/2)]
        else:
            x = int(len(self.path_points) / (len(self.sensors) + 1))
            point = self.path_points[x * (sensor_index + 1)]
        return point


    def find_sensor_position(self, pipe_point, parent_widget, min_distance=MIN_DISTANCE, above=True):
        dx, dy = 0, -60 if above else 60
        candidate = QtCore.QPoint(pipe_point.x() + dx, pipe_point.y() + dy)
        sensor_rect = QtCore.QRect(candidate.x(), candidate.y(), 110, 45)
        # Проверяем пересечения с другими объектами
        for obj in parent_widget.objects:
            if isinstance(obj, QPipe) or isinstance(obj, QSensor):
                continue
            obj_rect = obj.get_rect().adjusted(-min_distance, -min_distance, min_distance, min_distance)
            if sensor_rect.intersects(obj_rect):
                return None  # Мешает объект
        return candidate

    def contains(self, point, index=None):
        for path_point in self.path_points:
            rect = QRect(path_point.x() - 15, path_point.y() - 15, 30, 30)
            if not index and rect.contains(point):
                return rect.contains(point)
            else:
                if rect.contains(point) and rect.contains(point):
                    return path_point
        return False

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
        # pen = QtGui.QPen(QtCore.Qt.darkGreen, 10)
        # painter.setPen(pen)
        # for i in range(len(path_points) - 1):
        #     painter.drawLine(path_points[i], path_points[i+1])

    def build_path(self, start, end, obstacles):
        # Вычисляем расстояние между концами трубы
        distance = (start - end).manhattanLength()
        # Динамически выбираем размер сетки
        # if distance < 2000:
        #     grid_size = 20
        # elif distance < 3000:
        #     grid_size = 40
        # elif distance < 4000:
        #     grid_size = 80
        # else:
        #     grid_size = 120
        grid_size = 20
        # Создаем сетку по размерам области
        min_x = 0
        max_x = self.parent_widget.scene_width
        min_y = 0
        max_y = self.parent_widget.scene_height

        grid_width = int((max_x - min_x) / grid_size) + 1
        grid_height = int((max_y - min_y) / grid_size) + 1

        # Создаем массив ячеек
        grid = [[0 for _ in range(grid_width)] for _ in range(grid_height)]

        # Помечаем ячейки, занятые препятствиями
        for rect in obstacles:
            if rect != self.in_point.parent and rect != self.out_point.parent:
                 # Получаем индексы входной и выходной точки
                in_x = int((self.in_point.get_pos().x() - min_x) / grid_size)
                in_y = int((self.in_point.get_pos().y() - min_y) / grid_size)
                out_x = int((self.out_point.get_pos().x() - min_x) / grid_size)
                out_y = int((self.out_point.get_pos().y() - min_y) / grid_size)
                # Определяем диапазон ячеек, покрывающих препятствие
                start_x_idx = int((rect.left() - min_x) / grid_size)
                end_x_idx = int((rect.right() - min_x) / grid_size)
                start_y_idx = int((rect.top() - min_y) / grid_size)
                end_y_idx = int((rect.bottom() - min_y) / grid_size)
                for y in range(start_y_idx, end_y_idx + 1):
                    for x in range(start_x_idx, end_x_idx + 1):
                        # Не помечаем вход и выход как препятствия
                        if (x, y) in [(in_x, in_y), (out_x, out_y)]:
                            continue
                        grid[y][x] = 1
                        # ... буферные клетки, но тоже с проверкой ...
                        if x - 1 >= 0 and (x-1, y) not in [(in_x, in_y), (out_x, out_y)]:
                            grid[y][x - 1] = 1
                # start_x_idx = int((rect.left() - min_x) / grid_size)
                # end_x_idx = int((rect.right() - min_x) / grid_size)
                # start_y_idx = int((rect.top() - min_y) / grid_size)
                # end_y_idx = int((rect.bottom() - min_y) / grid_size)
                # for y in range(start_y_idx, end_y_idx + 1):
                #     for x in range(start_x_idx, end_x_idx + 1):
                #         if 0 <= y < grid_height and 0 <= x < grid_width:
                #             grid[y][x] = 1  # 1 — препятствие

        # Запускаем A* или BFS
        path_cells = self.a_star(grid, start, end, min_x, min_y, grid_size)
        # Преобразуем ячейки в точки
        path_points = [self.cell_to_point(x, y, min_x, min_y, grid_size) for x, y in path_cells]
        path_points.insert(0, start)
        # path_points[0] = QtCore.QPoint(path_points[0].x() -10, path_points[0].y())
        # path_points[-1] = QtCore.QPoint(path_points[-1].x() -10, path_points[-1].y())
        path_points[-1] = end
        return path_points



    def a_star(self, grid, start_point, end_point, min_x, min_y, grid_size):
        from collections import deque

        def to_grid(p):
            x = int((p.x() - min_x) / grid_size)
            y = int((p.y() - min_y) / grid_size)
            return x, y

        start = to_grid(start_point)
        end = to_grid(end_point)

        # Прямое и обратное направления
        open_fwd = []
        open_bwd = []
        heapq.heappush(open_fwd, (0, start))
        heapq.heappush(open_bwd, (0, end))
        came_from_fwd = {}
        came_from_bwd = {}

        g_fwd = {start: 0}
        g_bwd = {end: 0}

        closed_fwd = set()
        closed_bwd = set()

        meeting = None

        while open_fwd and open_bwd:
            # Шаг вперед из старта
            _, current_fwd = heapq.heappop(open_fwd)
            closed_fwd.add(current_fwd)

            for neighbor in self.get_neighbors(grid, current_fwd):
                if neighbor in closed_fwd:
                    continue
                tentative_g = g_fwd[current_fwd] + 1
                if neighbor not in g_fwd or tentative_g < g_fwd[neighbor]:
                    came_from_fwd[neighbor] = current_fwd
                    g_fwd[neighbor] = tentative_g
                    heapq.heappush(open_fwd, (tentative_g + self.heuristic(neighbor[0], neighbor[1], end[0], end[1]), neighbor))
                if neighbor in closed_bwd:
                    meeting = neighbor
                    break
            if meeting:
                break

            # Шаг назад из финиша
            _, current_bwd = heapq.heappop(open_bwd)
            closed_bwd.add(current_bwd)

            for neighbor in self.get_neighbors(grid, current_bwd):
                if neighbor in closed_bwd:
                    continue
                tentative_g = g_bwd[current_bwd] + 1
                if neighbor not in g_bwd or tentative_g < g_bwd[neighbor]:
                    came_from_bwd[neighbor] = current_bwd
                    g_bwd[neighbor] = tentative_g
                    heapq.heappush(open_bwd, (tentative_g + self.heuristic(neighbor[0], neighbor[1], start[0], start[1]), neighbor))
                if neighbor in closed_fwd:
                    meeting = neighbor
                    break
            if meeting:
                break

        # Если встреча найдена
        if meeting:
            path_fwd = self.reconstruct_path(came_from_fwd, meeting)
            path_bwd = self.reconstruct_path(came_from_bwd, meeting)
            path_bwd = path_bwd[::-1]
            full_path = path_fwd + path_bwd[1:]  # убрать дублирование meeting
            return full_path
        return []  # нет маршрута

    def get_rect(self):
        return self.path_points

    def delete(self):
        if self.in_point.parent != None:
            self.in_point.pipe = None
            self.in_point = None
        if self.out_point != None:
            self.out_point.pipe = None
            self.out_point = None
        if len(self.sensors) != 0:
            for sensor in self.sensors:
                sensor.delete()
            self.sensors = []
        self.parent_widget.pipes.remove(self)
        self.process_scheme.remove_element(self.logic_element.index)


class QPipeIntersection(DraggableObject):
    #def __init__(self, mode='split', label=''):
    def __init__(self, x, y, logic_element, process_scheme, parent_widget, tag='',
                 mode='split'):
        super().__init__(x, y, parent_widget, tag=tag, size=40, logic_element=logic_element, process_scheme=process_scheme)
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

    
class QSensor:
    SENSOR_UNITS = {
        "temperature": "°C",
        "pressure": "бар",
        "flow": "м³/ч",
        # Добавьте другие типы по необходимости
    }

    def __init__(self, x, y, parent_widget, logic_element, process_scheme, pipe, unit=None):
        self.position = QtCore.QPoint(x, y)
        self.width = 110
        self.height = 45
        self.size = max(self.width, self.height)  # Для совместимости с логикой редактора
        self.process_scheme = process_scheme
        self.pipe:QPipe = pipe
        self.pipe.sensors.append(self)
        self.logic_element:Sensor = logic_element
        self.process_scheme.sensors.append(self.logic_element)
        self.pipe.logic_element.sensors.append(self.logic_element)
        self.value = 0
        self.parent_widget = parent_widget
        # Автоматически определить единицу измерения, если не задана явно
        if unit is not None:
            self.unit = unit
        else:
            sensor_type = getattr(self.logic_element, "sensor_type", None)
            self.unit = self.SENSOR_UNITS.get(sensor_type, "")
        self.model = ModelSettings(self)
        #asd


    def work(self):
        self.value = self.logic_element.value

    def get_rect(self):
        """Возвращает QRect, занимаемый сенсором."""
        return QtCore.QRect(self.position.x(), self.position.y(), self.width, self.height)

    def contains(self, point):
        """Проверяет, находится ли точка (QPoint) внутри сенсора."""
        return self.get_rect().contains(point)

    def get_pos(self):
        """Возвращает позицию (левый верхний угол)."""
        return self.position

    def move_to(self, x, y):
        """Перемещает сенсор в новую позицию."""
        self.position = QtCore.QPoint(x, y)

    def delete(self):
        """Удаляет сенсор из редактора (если нужно)."""
        if self in self.parent_widget.objects:
            self.parent_widget.objects.remove(self)

    def paint(self, painter):
        # Основной прямоугольник
        rect = QtCore.QRect(self.position.x(), self.position.y(), self.width, self.height)
        painter.setPen(QtCore.Qt.black)
        painter.setBrush(QtGui.QColor(240, 240, 240))
        painter.drawRect(rect)
        # Пунктирная линия
        if self.pipe:
            # Найти индекс сенсора в списке трубы
            if hasattr(self.pipe, 'sensors'):
                idx = self.pipe.sensors.index(self)
                total = len(self.pipe.sensors)
                attach_point = self.pipe.get_sensor_attach_point(idx, total)
                if attach_point:
                    center = QtCore.QPoint(self.position.x() + self.width // 2, self.position.y() + self.height // 2)
                    pen = QtGui.QPen(QtCore.Qt.black, 1, QtCore.Qt.DashLine)
                    painter.setPen(pen)
                    painter.drawLine(center, attach_point)
        # Идентификатор (верхняя строка)
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtCore.Qt.black)
        sensor_id = str(getattr(self.logic_element, "index", "—"))
        painter.drawText(
            QtCore.QRect(self.position.x(), self.position.y(), self.width, 18),
            QtCore.Qt.AlignCenter,
            sensor_id
        )

        # Линия-разделитель
        painter.drawLine(
            self.position.x(), self.position.y() + 18,
                               self.position.x() + self.width, self.position.y() + 18
        )

        # Значение (синим)
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QtCore.Qt.blue)
        # Получаем значение из логического элемента
        value = getattr(self.logic_element, "value", None)
        if value is None and hasattr(self.logic_element, "get_value"):
            value = self.logic_element.get_value()
        if value is None:
            value = "—"
        painter.drawText(
            QtCore.QRect(self.position.x() + 4, self.position.y() + 20, self.width - 8, 20),
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            f"{value} {self.unit}"
        )



# --- Класс для сетки и привязки ---
class WidgetWithObjects(QtWidgets.QOpenGLWidget):
    def __init__(self, controller, process_scheme:ProcessScheme, map=None, parent=None):
        super().__init__(parent)
        self.process_scheme = process_scheme
        self.controller = controller
        self.setGeometry(0, 0, 1300, 800)
        self.objects:list[DraggableObject] = []
        self.selected_object = None
        self.settings_selected_object = None
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
        self.scene_width = 4000
        self.scene_height = 4000
        self.controller.element_changed.connect(self.set_selected_element)
        self.map:MapWidget = map
        self.pipes = []

    def pos_scene(self, event):
        scene_pos = event.pos() - self.scene_offset
        return scene_pos

    def clamp_scene_offset(self, offset):
        # Размеры рабочей области
        scene_width = self.scene_width
        scene_height = self.scene_height

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

    def paintGL(self):
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glColor3f(0.0, 0.6, 0.0)
        glLineWidth(8)
        self.map.update()
        if len(self.pipes) != 0:
            for pipe in self.pipes:
                if len(pipe.path_points) < 2:
                    continue
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                glOrtho(0, self.width(), self.height(), 0, -1, 1)
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                glBegin(GL_LINE_STRIP)
                for point in pipe.path_points:
                    if (0-self.scene_offset.x() < point.x() < self.width() - self.scene_offset.x() and
                            0-self.scene_offset.y() < point.y() < self.height() - self.scene_offset.y()):
                        glVertex2f(point.x() + self.scene_offset.x(), point.y() + self.scene_offset.y())
                glEnd()

        painter = QtGui.QPainter(self)
        painter.save()
        painter.translate(self.scene_offset)
        self.draw_grid(painter)
        for obj in self.objects:
            obj.paint(painter)
            if hasattr(obj, "image") and not obj.image.isNull():
                painter.drawPixmap(obj.position.x(), obj.position.y(), obj.size, obj.size, obj.image)

        # --- Подсветка выбранного для настроек объекта ---
        if self.settings_selected_object is not None:
            obj = self.settings_selected_object
            if type(obj) == QPipe:
                pass
            else:
                # Для обычных объектов
                if hasattr(obj, "get_rect"):
                    rect = obj.get_rect()
                else:
                    # запасной вариант
                    rect = QtCore.QRect(obj.position.x(), obj.position.y(), obj.size, obj.size)

                highlight_pen = QtGui.QPen(QtCore.Qt.red, 2, QtCore.Qt.DashLine)
                painter.setPen(highlight_pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRect(rect)

        painter.restore()

    def draw_grid(self, painter):
        pen = QtGui.QPen(QColor(200, 200, 200))
        painter.setPen(pen)
        # Рисуем вертикальные линии по всей сцене
        for x in range(0, self.scene_width, self.grid_size):
            painter.drawLine(x, 0, x, self.scene_height)
        # Рисуем горизонтальные линии по всей сцене
        for y in range(0, self.scene_height, self.grid_size):
            painter.drawLine(0, y,self.scene_width, y)

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
        scene_pos = pos - self.scene_offset
        for obj in reversed(self.objects):
            if type(obj) ==QSensor:
                continue
            else:
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
                    if point.contains(scene_pos):
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
                    new_obj = QPump(pos.x(), pos.y(), parent_widget=self, logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == 'QSensor':
                    # scene_pos = self.pos_scene(event)
                    # for obj in reversed(self.objects):
                    #     if type(obj) == QPipe:
                    #         if obj.contains(scene_pos):
                    #             path_point:QPoint = obj.contains(scene_pos, index=True)
                    #             logic_obj = Sensor(sensor_type="P")
                    #             new_obj = QSensor(path_point.x(), path_point.y(), parent_widget=self,
                    #                               logic_element=logic_obj, process_scheme=self.process_scheme, pipe=obj)
                    #             break
                    scene_pos = self.pos_scene(event)
                    for obj in reversed(self.objects):
                        if type(obj) == QPipe:
                            if type(obj) == QPipe:
                                if obj.contains(scene_pos):
                                    # Добавляем сенсор в список трубы
                                    if not hasattr(obj, 'sensors'):
                                        obj.sensors = []
                                    logic_obj = Sensor(sensor_type="P")
                                    # x = len(obj.sensors)
                                    # obj.sensors.append(None)  # временно, чтобы узнать индекс
                                    # sensor_index = len(obj.sensors) - 1
                                    # total_sensors = len(obj.sensors)
                                    # del obj.sensors[x]
                                    # attach_point = obj.get_sensor_attach_point(sensor_index, total_sensors)
                                    attach_point = scene_pos
                                    # Найти позицию для сенсора (над или под трубой)
                                    pos = obj.find_sensor_position(attach_point, self, above=True)
                                    if pos is None:
                                        pos = obj.find_sensor_position(attach_point, self, above=False)
                                    if pos is None:
                                        # Не удалось разместить сенсор
                                        obj.sensors.pop()
                                        return
                                    new_obj = QSensor(pos.x(), pos.y(), parent_widget=self,
                                                         logic_element=logic_obj, process_scheme=self.process_scheme, pipe=obj)
                                    # obj.sensors[sensor_index] = new_obj
                                    # self.objects.append(new_obj)
                                    self.selected_element = None
                                    self.controller.set_element(None)
                                    self.unsetCursor()
                                    self.update()
                                    break
                        else:
                            continue
                elif self.selected_element == "QMov":
                    logic_obj = MovElement()
                    new_obj = QMov(pos.x(), pos.y(), parent_widget=self, logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QBoiler":
                    logic_obj = BoilerElement()
                    new_obj = QBoiler(pos.x(), pos.y(), parent_widget=self, logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QPipeIntersection|Split":
                    logic_obj = PipeIntersectionElement(mode='split')
                    new_obj = QPipeIntersection(pos.x(), pos.y(), parent_widget=self, logic_element=logic_obj, process_scheme=self.process_scheme)
                elif self.selected_element == "QPipeIntersection|Merge":
                    logic_obj = PipeIntersectionElement(mode='merge')
                    new_obj = QPipeIntersection(pos.x(), pos.y(), parent_widget=self, logic_element=logic_obj, process_scheme=self.process_scheme, mode='merge')
                elif self.selected_element == "QPipe":
                    point, obj = self.get_connection_point_at((self.pos_scene(event)))
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
                                                 logic_element=logic_obj,
                                                 process_scheme=self.process_scheme, parent_widget=self)

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
                elif self.selected_element == "QFlowSource":
                    logic_obj = FlowSourceElement()
                    new_obj = QFlowSource(pos.x(), pos.y(), parent_widget=self, logic_element=logic_obj, process_scheme=self.process_scheme)

                else:
                    new_obj = DraggableObject(pos.x(), pos.y())
                # Привязка к сетке
                new_obj.position = self.snap_to_grid(new_obj.position)
                self.objects.append(new_obj)
                self.selected_element = None
                self.controller.set_element(None)
                self.unsetCursor()
                self.update()
            if event.button() == QtCore.Qt.RightButton:
                # Отмена выбора элемента по правому клику
                self.selected_element = None
                self.controller.set_element(None)
                self.unsetCursor()
                self.update()
                return
        if event.button() == QtCore.Qt.MiddleButton:
            self.dragging = True
            self.drag_start_pos = event.pos()
            self.offset_at_drag_start = self.scene_offset
        elif event.button() == QtCore.Qt.LeftButton:
            # Перетаскивание объектов
            scene_pos = self.pos_scene(event)
            for obj in reversed(self.objects):
                if obj.contains(scene_pos):
                    self.selected_object = obj
                    obj.dragging = True
                    self.offset = scene_pos - obj.position
                    self.update()
                    break

    def mouseDoubleClickEvent(self, event):
        scene_pos = self.pos_scene(event)
        # Ищем объект под курсором
        for obj in reversed(self.objects):
            if obj.contains(scene_pos):
                # Сообщаем контроллеру, что этот объект выбран для настроек
                self.controller.set_settings_object(obj)
                self.settings_selected_object = obj
                self.update()
                break
        else:
            # Если ни один объект не найден, можно сбросить выбор
            self.controller.set_settings_object(None)
            self.settings_selected_object = None
            self.update()


    def mouseMoveEvent(self, event):
        if self.selected_object and self.selected_object.dragging:
            scene_pos = self.pos_scene(event)
            new_pos = scene_pos - self.offset
            new_pos = self.snap_to_grid(new_pos)
            # Ограничение по границам сцены с учетом margin
            margin = CONNECTION_MARGIN
            if type(self.selected_object) == QSensor:
                self.selected_object : QSensor
                max_x = self.scene_width - self.selected_object.width - margin
                max_y = self.scene_height - self.selected_object.height - margin
            else:
                max_x = self.scene_width - self.selected_object.size - margin
                max_y = self.scene_height - self.selected_object.size - margin
            new_pos.setX(max(margin, min(new_pos.x(), max_x)))
            new_pos.setY(max(margin, min(new_pos.y(), max_y)))
            # Проверка на пересечение с другими объектами
            if type(self.selected_object) == QSensor:
                new_rect = QtCore.QRect(new_pos.x(), new_pos.y(), self.selected_object.width, self.selected_object.height)
            else:
                new_rect = QtCore.QRect(new_pos.x(), new_pos.y(), self.selected_object.size, self.selected_object.size)
            min_distance = MIN_DISTANCE  # минимальное расстояние между объектами
            can_move = True
            for obj in self.objects:
                if obj is self.selected_object or type(obj) == QPipe:
                    continue
                obj_rect = obj.get_rect()
                rect = QtCore.QRect(obj_rect.x(), obj_rect.y(), obj_rect.width(), obj_rect.height() -20)
                obj_rect = rect.adjusted(-min_distance, -min_distance, min_distance, min_distance)
                if new_rect.intersects(obj_rect):
                    can_move = False
                    break
            if can_move:
                self.selected_object.position = new_pos
                self.update()
            # # Перетаскивание объекта
            # scene_pos = self.pos_scene(event)
            # new_pos = scene_pos - self.offset
            # new_pos = self.snap_to_grid(new_pos)
            # self.selected_object.position = new_pos
            # self.update()
        if self.dragging:
            # Панорамирование сцены
            delta = event.pos() - self.drag_start_pos
            new_offset = self.offset_at_drag_start + delta
            # Привязка смещения к сетке
            new_offset = self.clamp_scene_offset(new_offset)
            self.scene_offset = new_offset
            self.update()
            # new_offset = self.snap_to_grid(new_offset)
            # self.scene_offset = new_offset
            # self.update()

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
            self.process_scheme.print_chains()
            for x in self.objects:
                pass
                # print(f'Element ---------------------{x}')
                # x:DraggableObject
                # print(f'IN ---{x.in_point}')
                # print(f' in_element {x.in_point.pipe}')
                # print(f'OUT ---{x.out_point}')
                # print(f' out_element {x.out_point.pipe}')
                # print('-------------------------------------------------------------')
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

    @staticmethod
    def paint_pipe(path_points):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glColor3f(0.0, 0.6, 0.0)
        glLineWidth(8)
        if len(path_points) < 2:
            return
        glBegin(GL_LINE_STRIP)
        for point in path_points:
            glVertex2f(point.x(), point.y())
        glEnd()



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
    @staticmethod
    def map_to_scene(map_point, scene_size, map_size):
        """Переводит координаты с миникарты в координаты сцены."""
        scale_x = scene_size[0] / map_size[0]
        scale_y = scene_size[1] / map_size[1]
        scene_x = map_point.x() * scale_x
        scene_y = map_point.y() * scale_y
        return QtCore.QPoint(int(scene_x), int(scene_y))

    @staticmethod
    def get_view_center(scene_offset, view_size):
        """Вычисляет координаты центра видимой области сцены"""
        center_x = -scene_offset.x() + view_size[0] // 2
        center_y = -scene_offset.y() + view_size[1] // 2
        return QtCore.QPoint(center_x, center_y)

    def __init__(self, redactor, parent=None):
        super().__init__(parent)
        self.redactor = redactor  # ссылка на основной виджет сцены
        self.setMinimumSize(200, 200)  # можно изменить под ваши нужды

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            map_click = event.pos()
            # Размеры миникарты и сцены
            map_size = (self.width(), self.height())
            scene_size = (self.redactor.scene_width, self.redactor.scene_height)
            view_size = (self.redactor.width(), self.redactor.height())

            # Центр видимой области на миникарте
            current_center_scene = self.get_view_center(self.redactor.scene_offset, view_size)
            current_center_map = self.scene_to_map(current_center_scene, scene_size, map_size)

            # Дельта на миникарте
            delta_map = map_click - current_center_map

            # Дельта в координатах сцены
            scale_x = scene_size[0] / map_size[0]
            scale_y = scene_size[1] / map_size[1]
            delta_scene = QtCore.QPoint(int(delta_map.x() * scale_x), int(delta_map.y() * scale_y))

            # Новый центр сцены
            new_center_scene = current_center_scene + delta_scene

            # Новый offset, чтобы центр оказался в нужной точке
            new_offset = QtCore.QPoint(
                -new_center_scene.x() + view_size[0] // 2,
                -new_center_scene.y() + view_size[1] // 2
            )
            # Ограничить offset по границам сцены
            new_offset = self.redactor.clamp_scene_offset(new_offset)
            self.redactor.scene_offset = new_offset
            self.redactor.update()

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
                if type(obj) == QPipe:
                    # pass
                    pen = QtGui.QPen(QtCore.Qt.darkGreen, 1)
                    painter.setPen(pen)
                    for i in range(len(obj.path_points) - 1):
                        map_pos = self.scene_to_map(obj.path_points[i],
                                                    (self.redactor.scene_width, self.redactor.scene_height),
                                                    (self.width(), self.height()))
                        map_pos = QPointF(map_pos.x(), map_pos.y()-1.5)

                        map_pos2 = self.scene_to_map(obj.path_points[i+1],
                                                     (self.redactor.scene_width, self.redactor.scene_height),
                                                     (self.width(), self.height()))
                        map_pos2 = QPointF(map_pos2.x(), map_pos2.y()-1.5)
                        painter.drawLine(map_pos, map_pos2)
                elif type(obj) == QSensor:
                    map_pos = self.scene_to_map(obj.position,
                                                (self.redactor.scene_width, self.redactor.scene_height),
                                                (self.width(), self.height()))
                    painter.setPen(QtCore.Qt.red)
                    painter.setBrush(QtCore.Qt.red)
                    painter.drawEllipse(map_pos, 1, 1)
                else:
                    map_pos = self.scene_to_map(obj.position,
                                                (self.redactor.scene_width, self.redactor.scene_height),
                                                (self.width(), self.height()))
                    painter.setPen(QtCore.Qt.blue)
                    painter.setBrush(QtCore.Qt.blue)
                    painter.drawEllipse(map_pos, 2, 2)


class ControlMenu(QtWidgets.QToolBar):
    def __init__(self,name, parent_widget):
        super().__init__(name, parent_widget)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)
        self.setStyleSheet("background-color: rgb(177, 177, 177);")
        self.parent_widget = parent_widget
        # self.setAllowedAreas(QtCore.Qt.TopDockWidgetArea)
        self.action1 = QAction(QIcon("icon/init_on.png" if self.parent_widget.process_scheme.chain_ready else "icon/init_off.png"), "Инструмент 1", self)
        self.action2 = QAction(QIcon("icon/def.png"), "Инструмент 2", self)
        self.action3 = QAction(QIcon("icon/def.png"), "Инструмент 3", self)

        self.addAction(self.action1)
        self.addAction(self.action2)
        self.addAction(self.action3)

        self.action1.triggered.connect(self.action1_clicked)

    @pyqtSlot()
    def action1_clicked(self):
        if not self.parent_widget.process_scheme.chain_ready:
            self.parent_widget.process_scheme.initialize_chains()



    def addAction(self, action):
        super().addAction(action)
        self.addSeparator()


class ModelSettings:
    def __init__(self, element):
        if type(element) == QSensor:
            self.logic_element:Sensor = element.logic_element
        else:
            self.logic_element:BaseElement = element.logic_element
        self.index = self.logic_element.index
        self.parameters:dict = self.logic_element.get_parameters()

    def get_parameters(self):
        self.parameters = self.logic_element.get_parameters()
        return self.parameters


class SettingsMenu(QtWidgets.QDockWidget):
    def __init__(self,parent_widget):
        super().__init__('Настройки', parent_widget)
        self.setMinimumSize(QtCore.QSize(220, 300))
        self.setStyleSheet("background-color: rgb(177, 177, 177);")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        self._widget = QtWidgets.QWidget()
        self._layout = QtWidgets.QFormLayout(self._widget)
        self.setWidget(self._widget)

        self.current_element = None
        self.current_model = None
        self.controller = parent_widget.controller
        self.controller.settings_object_changed.connect(self.set_element)


        self._widget = QtWidgets.QWidget()
        self._v_layout = QtWidgets.QVBoxLayout(self._widget)

        # Блок информации об объекте (то, что из parameters['object'])
        self.info_layout = QtWidgets.QFormLayout()
        self._v_layout.addLayout(self.info_layout)

        # Разделитель
        self._v_layout.addSpacing(8)
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self._v_layout.addWidget(line)

        # Блок редактируемых параметров
        self.form_layout = QtWidgets.QFormLayout()
        self._v_layout.addLayout(self.form_layout)

        self.setWidget(self._widget)

        self.current_element = None
        self.current_model = None
        self.controller = parent_widget.controller
        self.controller.settings_object_changed.connect(self.set_element)




    def set_element(self, element):
        self.current_element = element
        if element is None:
            self._clear_info()
            self._clear_form()
            return

        # Берём ModelSettings из объекта
        if not hasattr(element, "model") or element.model is None:
            element.model = ModelSettings(element)
        self.current_model = element.model

        self._rebuild()

    def _clear_info(self):
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()


    def _clear_form(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rebuild(self):
        self._clear_info()
        self._clear_form()

        params = self.current_model.get_parameters()

        # 1) Паспорт объекта: params.get('object')
        passport = params.get('object')
        if isinstance(passport, dict):
            self._build_object_info(passport)

        #self._rebuild_form()

        # 2) Остальные параметры — как раньше, кроме 'object'
        for name, raw in params.items():
            if name == 'object':
                continue
            self._add_param_widget(name, raw)


    def _build_object_info(self, passport: dict):
        """
        passport = {
            'object': {...},
            'tag': {...},
            'index': {...},
            ...
        }
        """
        # Имя объекта
        obj_meta = passport.get('object')
        if obj_meta is not None:
            # value = self (объект); можно красиво отформатировать
            obj = obj_meta.get('value')
            # Например: QPipe (#4) или просто тип
            type_name = type(obj).__name__ if obj is not None else "—"
            label_text = obj_meta.get('label', 'Объект')
            self.info_layout.addRow(
                QtWidgets.QLabel(label_text + ":"),
                QtWidgets.QLabel(type_name)
            )

        # Тег (общий)
        tag_meta = passport.get('tag')
        if tag_meta is not None:
            tag_val = tag_meta.get('value', '')
            label_text = tag_meta.get('label', 'Тег')
            self.info_layout.addRow(
                QtWidgets.QLabel(label_text + ":"),
                QtWidgets.QLabel(str(tag_val))
            )

        # Индекс
        idx_meta = passport.get('index')
        if idx_meta is not None:
            idx_val = idx_meta.get('value', '')
            label_text = idx_meta.get('label', 'Индекс')
            self.info_layout.addRow(
                QtWidgets.QLabel(label_text + ":"),
                QtWidgets.QLabel(str(idx_val))
            )

    def _add_param_widget(self, name, raw):
        # raw может быть:
        # 1) dict с value/type/label
        # 2) голое значение
        if isinstance(raw, dict) and "value" in raw and "type" in raw:
            meta = raw
            value = raw.get("value")
            ptype = meta.get("type")
            label_text = meta.get("label", name)
        else:
            meta = {
                "value": raw,
                "type": type(raw).__name__,
                "label": name
            }

        value = meta.get("value")
        ptype = meta.get("type")
        label_text = meta.get("label", name)

        label = QtWidgets.QLabel(label_text)

        # здесь создаёшь нужный редактор (QLineEdit / QDoubleSpinBox / QCheckBox и т.д.)
        # пока можно оставить простой вариант:
        editor = self._create_editor_for_type(name, value, meta, ptype)
        self.form_layout.addRow(label, editor)

    def _create_editor_for_type(self, name, value, meta, ptype):
        elem = self.current_model.logic_element

        if ptype == "bool":
            cb = QtWidgets.QCheckBox()
            cb.setChecked(bool(value))
            cb.stateChanged.connect(
                lambda state, n=name: self._on_param_changed(n, bool(state))
            )
            return cb

        elif ptype in ("float", "double"):
            sb = QtWidgets.QDoubleSpinBox()
            sb.setStyleSheet("background-color: rgb(255, 255, 255);")
            sb.setDecimals(4)
            sb.setRange(meta.get("min", -1e9), meta.get("max", 1e9))
            sb.setSingleStep(meta.get("step", 0.1))
            sb.setValue(float(value))
            sb.valueChanged.connect(
                lambda val, n=name: self._on_param_changed(n, float(val))
            )
            return sb

        elif ptype in ("int", "integer"):
            sb = QtWidgets.QSpinBox()
            sb.setStyleSheet("background-color: rgb(255, 255, 255);")
            sb.setRange(int(meta.get("min", -1e9)), int(meta.get("max", 1e9)))
            sb.setSingleStep(int(meta.get("step", 1)))
            sb.setValue(int(value))
            sb.valueChanged.connect(
                lambda val, n=name: self._on_param_changed(n, int(val))
            )
            return sb

        elif ptype == "choice":
            combo = QtWidgets.QComboBox()
            combo.setStyleSheet("background-color: rgb(255, 255, 255);")
            choices = meta.get("choices", [])
            combo.addItems(choices)
            if value in choices:
                combo.setCurrentText(value)
            combo.currentTextChanged.connect(
                lambda text, n=name: self._on_param_changed(n, text)
            )
            return combo

        else:
            # строка по умолчанию
            le = QtWidgets.QLineEdit(str(value))
            le.editingFinished.connect(
                lambda n=name, w=le: self._on_param_changed(n, w.text())
            )
            return le

    def _on_param_changed(self, name, value):
        elem = self.current_model.logic_element

        # 1. Если есть сеттер set_<name>, используем его
        setter_name = f"set_{name}"
        if hasattr(elem, setter_name) and callable(getattr(elem, setter_name)):
            getattr(elem, setter_name)(value)
            return

        # 2. Иначе пробуем напрямую свойство
        if hasattr(elem, name):
            setattr(elem, name, value)
            return
        # при желании можно логировать, если параметр не смог примениться


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
        self.mapWidget.setMinimumSize(QtCore.QSize(220, 120))
        self.mapWidget.setStyleSheet("background-color: rgb(177, 177, 177);")
        self.mapWidget.setAllowedAreas(QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea)
        self.mapWidgetContents = MapWidget(self.redactor)

        self.mapWidget.setWidget(self.mapWidgetContents)
        self.redactor.map = self.mapWidgetContents

        self.control_menu = ControlMenu('',self)
        self.addToolBar(self.control_menu)


        # Настройка элементов для выбора
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
            ("QPipeIntersection|Split", "icon/PipeIntersection.png"),
            ("QPipeIntersection|Merge", "icon/PipeIntersection_merge.png"),
            ('QSensor', "icon/Sensor.png" ),
            ('QFlowSource', "icon/FlowSource.png")
        ]

        for name, icon_path in items:
            item = QtWidgets.QListWidgetItem(QtGui.QIcon(icon_path), name)
            self.dockWidgetContents.addItem(item)
        self.dockWidgetContents.currentItemChanged.connect(self.item_changed)
        self.dockWidget.setWidget(self.dockWidgetContents)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockWidget)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.mapWidget)
        self.splitDockWidget(self.mapWidget, self.dockWidget, QtCore.Qt.Vertical)
        self.mapWidget.resize(220, 100)

        self.resizeDocks([self.mapWidget, self.dockWidget], [200, 300], QtCore.Qt.Vertical)

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_sensors)
        self.update_timer.start(500)  # обновлять каждые 500 мс (0.5 сек)

        self.settings_menu = SettingsMenu(self)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.settings_menu)


    def update_sensors(self):
        for obj in self.redactor.objects:
            if isinstance(obj, QSensor):
                obj.work()
        self.redactor.update()  # перерисовать сцену, если нужно

        self.control_menu.action1.setIcon(QIcon("icon/init_on.png" if self.process_scheme.chain_ready else "icon/init_off.png"))


    def item_changed(self, current, previous):
        if current:
            self.controller.set_element(current.text())


# --- Запуск ---
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


