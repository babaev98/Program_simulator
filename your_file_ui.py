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

    def __init__(self, start_point, end_point, start_logic, end_logic, logic_element=None,
                 process_scheme=None, parent_widget=None):
        super().__init__(0, 0, tag='', size=0, color=QtGui.QColor(0,0,0,0))
        self.start_point = start_point
        # self.end_point = end_point
        # self.in_point = start_point
        self.out_point = end_point
        self.logic_element = logic_element
        self.parent_widget = parent_widget
        if self.logic_element and process_scheme:
            process_scheme.add_element(self.logic_element)
        if start_logic and end_logic:
            self.logic_element.add_in_element(start_logic)
            self.logic_element.add_out_element(end_logic)
            start_logic.add_out_element(self.logic_element)
            end_logic.add_in_element(self.logic_element)

    def paint(self, painter):
        painter.setBrush(QtCore.Qt.NoBrush)
        pen = QtGui.QPen(QtCore.Qt.darkBlue, 8)
        painter.setPen(pen)
        p1 = self.start_point.get_pos_pipe()
        p2 = self.end_point.get_pos_pipe()
        # Собираем препятствия
        obstacles = []
        parent_widget = self.parent_widget
        connect_obj = getattr(self, 'connect_obj', None)

        if parent_widget:
            for obj in parent_widget.objects:
                if obj is self:
                    continue
                if connect_obj and obj is connect_obj:
                    continue
                rect = getattr(obj, "get_rect", lambda: None)()
                if isinstance(rect, QtCore.QRect) and rect.width() > 0 and rect.height() > 0:
                    obstacles.append(rect)

        # Построение маршрута с обходом препятствий
        path_points = QPipe.build_orthogonal_path(p1, p2, obstacles)

        # Рисуем линию по маршруту
        path = QtGui.QPainterPath()
        path.moveTo(path_points[0])
        for pt in path_points[1:]:
            path.lineTo(pt)
        painter.drawPath(path)