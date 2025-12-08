import random
from PyQt5.QtCore import QObject, pyqtSignal

class ProcessScheme(QObject):
    chain_initialized = pyqtSignal()      # Сигнал: цепь построена
    chain_not_initialized = pyqtSignal()  # Сигнал: требуется новая

    def __init__(self):
        super().__init__()
        self.elements_dict = {}  # {index: element}
        self.next_index = 0
        self.chains = []  # Список цепей, каждая — список индексов
        self.chain_ready = False

    def remove_element(self, index):
        """Удалить элемент по индексу и обновить связи."""
        if index in self.elements_dict:
            # Удалить связи у других элементов
            for elem in self.elements_dict.values():
                if index in elem.in_indices:
                    elem.in_indices.remove(index)
                if index in elem.out_indices:
                    elem.out_indices.remove(index)
            # Удалить сам элемент
            del self.elements_dict[index]
            self.chain_ready = False
            self.chain_not_initialized.emit()

    def add_element(self, element):
        element.index = self.next_index
        self.elements_dict[self.next_index] = element
        self.next_index += 1
        self.chain_ready = False
        self.chain_not_initialized.emit()

    def connect(self, from_idx, to_idx):
        """Соединить элементы по индексам."""
        self.elements_dict[from_idx].add_out_index(to_idx)
        self.elements_dict[to_idx].add_in_index(from_idx)

    def find_start_elements(self):
        """Найти все элементы FlowSourceElement как начало цепей."""
        return [e for e in self.elements_dict.values() if isinstance(e, FlowSourceElement)]

    def build_chains(self):
        """Построить все возможные цепи (пути) от FlowSourceElement до стоков."""
        self.chains = []
        starts = self.find_start_elements()
        for start in starts:
            self._dfs_chain([start.index], set())

    def _dfs_chain(self, path, visited):
        current_idx = path[-1]
        visited = visited | {current_idx}
        current_elem = self.elements_dict[current_idx]
        if not current_elem.out_indices:
            self.chains.append(list(path))
            return
        for next_idx in current_elem.out_indices:
            if next_idx not in visited:
                self._dfs_chain(path + [next_idx], visited)

    def initialize_chains(self, p0=1.0, t0=20.0):
        """Присвоить давление и температуру первым элементам цепей, рассчитать сопротивления ветвей."""
        self.build_chains()
        for chain in self.chains:
            first_elem = self.elements_dict[chain[0]]
            first_elem.p_in = p0
            first_elem.t_in = t0
        # Пример: рассчитать сопротивления для всех PipeIntersectionElement
        for elem in self.elements_dict.values():
            if hasattr(elem, 'set_resistances') and hasattr(elem, 'out_indices'):
                resistances = []
                for out_idx in elem.out_indices:
                    # Найти цепь, начинающуюся с out_idx
                    for chain in self.chains:
                        if chain and chain[0] == out_idx:
                            r = sum(self.elements_dict[i].get_resistance() for i in chain)
                            resistances.append(r)
                elem.set_resistances(resistances)
        self.chain_ready = True
        self.chain_initialized.emit()

    def calculate(self, flow=1.0):
        """Задать расход первому элементу и вызвать work() у всех элементов."""
        if self.chains and self.chains[0]:
            first_elem = self.elements_dict[self.chains[0][0]]
            if hasattr(first_elem, 'set_flow'):
                first_elem.set_flow(flow)
        for idx in self.elements_dict:
            self.elements_dict[idx].work()


'''
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

'''



class BaseElement:#Базовый элемент
    @staticmethod
    def rattle(val:float, val_range:float) -> float:#Дребезг показаний
        val = val - val_range + random.uniform(0, val_range * 2)
        return val

    def __init__(self, in_indices=None, resistance:float=None):
        self.index = None  # Уникальный индекс, присваивается схемой
        self.in_indices = in_indices if in_indices is not None else []  # индексы входных элементов
        self.out_indices = []  # индексы выходных элементов (заполняются схемой)
        self.in_elements = []
        self.out_elements = []
        # Параметры процесса
        self.t_in = None
        self.p_in = None
        self.f_in = None
        self.t_out = None
        self.p_out = None
        self.f_out = None
        self._resistance = 0.0

    def add_in_index(self, idx):
        if idx not in self.in_indices:
            self.in_indices.append(idx)

    def add_out_index(self, idx):
        if idx not in self.out_indices:
            self.out_indices.append(idx)

    @property
    def resistance(self):
        return self._resistance

    @resistance.setter
    def resistance(self, value):
        self._resistance = value

    def get_resistance(self):
        return self.resistance

    def add_in_element(self, element):
        self.in_elements.append(element)

    def add_out_element(self, element):
        self.out_elements.append(element)

    def update_inputs(self):
        # Для простых случаев: берем параметры первого входного элемента
        if self.in_elements:
            self.t_in = self.in_elements[0].t_out
            self.p_in = self.in_elements[0].p_out
            self.f_in = self.in_elements[0].f_out

    def change_t(self):# Изменение температуры
        self.t_out = self.t_in

    def change_p(self):# Изменение давление
        self.p_out = self.p_in

    def change_f(self):# Изменение расхода
        self.f_out = self.f_in

    def work(self):# Вызов параметров изменения
        self.update_inputs()
        self.change_t()
        self.change_p()
        self.change_f()

    def depressurization(self, breach_percent=None):
        pass


class FlowSourceElement(BaseElement):
    """
    Источник расхода: задаёт f_out по сигналу от управляющего класса схемы.
    """
    def __init__(self, in_elements=None):
        super().__init__(in_elements)
        self.f_out = 0.0

    def set_flow(self, flow):
        self.f_out = flow

    def change_f(self):
        # Расход задаётся внешним сигналом, не пересчитывается
        pass

    def change_p(self):
        # Давление на выходе можно задать или рассчитать по схеме
        self.p_out = self.p_in if self.p_in is not None else 0.0

    def change_t(self):
        self.t_out = self.t_in


class Sensor:
    def __init__(self, sensor_type):
        self.sensor_type = sensor_type
        self.value = None
        self.index = None

    def update(self, value, rattle_range=0.0):
        # Обновить значение с учетом дребезга
        if rattle_range > 0:
            self.value = BaseElement.rattle(value, rattle_range)
        else:
            self.value = value

    def get(self):
        return self.value


class PipeElementElement(BaseElement):
    """
    Упрощённая труба с поддержкой датчиков.
    """
    def __init__(self, length, diameter):
        super().__init__()
        self.length = length
        self.diameter = diameter
        self.sensors = []
        self.breach = False
        self.breach_percent = 0.0


    def add_sensor(self, sensor):
        self.sensors.append(sensor)

    def update_sensors(self):
        # Передаём актуальные значения всем сенсорам
        for sensor in self.sensors:
            if sensor.sensor_type == 'pressure':
                sensor.update(self.p_out, rattle_range=0.1)
            elif sensor.sensor_type == 'flow':
                sensor.update(self.f_out, rattle_range=0.05)
            elif sensor.sensor_type == 'temperature':
                sensor.update(self.t_out, rattle_range=0.2)

    def change_p(self):
        dP = self._resistance * self.length * self.f_in
        if self.breach and self.breach_percent > 0:
            breach_factor = min(self.breach_percent, 1.0)
            dP += 5 * breach_factor * self.p_in
        self.p_out = self.p_in - dP

    def change_t(self):
        self.t_out = self.t_in

    def change_f(self):
        self.f_out = self.f_in
        if self.breach and self.breach_percent > 0:
            breach_factor = min(self.breach_percent, 1)
            lost_flow = self.f_in * breach_factor
            self.f_out = max(self.f_in - lost_flow, 0.0)

    def work(self):
        super().work()
        self.update_sensors()

    def depressurization(self, breach_percent = None):
        if breach_percent is not None:
            self.breach = True
            self.breach_percent = breach_percent

    def get_resistance(self):
        return self._resistance * self.length

class PipeChangeElement(BaseElement):
    """
    Сужение/расширение трубы.
    Меняет диаметр, пересчитывает скорость и потери давления.
    """
    def __init__(self, new_diameter, length=1.0):
        super().__init__()
        self.new_diameter = new_diameter  # Новый диаметр после сужения/расширения (м)
        self.length = length              # Длина участка с изменением диаметра (м)

    @property
    def resistance(self):
        # Сопротивление рассчитывается динамически, сеттер не нужен
        # Пример: чем сильнее сужение, тем больше сопротивление
        # (формула условная, подберите под задачу)
        if not self.in_elements or not hasattr(self.in_elements[0], 'diameter'):
            return 1.0  # дефолт
        d1 = self.in_elements[0].diameter
        d2 = self.new_diameter
        if d2 == 0:
            return float('inf')
        return 0.1 * abs((d1 - d2) / d1) * self.length

    @resistance.setter
    def resistance(self, value):
        # Сеттер не нужен, сопротивление считается автоматически
        pass

    def get_resistance(self):
        return self.resistance

    def change_f(self):
        # Расход сохраняется (если нет утечек)
        if self.in_elements:
            self.f_out = self.f_in

    def change_p(self):
        # Упрощённо: потери давления на сужении/расширении (формула Бернулли + локальные потери)
        if self.in_elements:
            rho = 1000  # кг/м3 (вода)
            S1 = (self.in_elements[0].f_in) / (self.f_in + 1e-9)  # старый расход/новый расход (почти всегда 1)
            v1 = self.f_in / (3.1415 * (self.in_elements[0].f_in / (self.f_in + 1e-9)) ** 2 / 4 + 1e-9)
            v2 = self.f_in / (3.1415 * (self.new_diameter / 2) ** 2 + 1e-9)
            # Потери на сужении/расширении (локальные)
            ksi = abs(1 - (self.new_diameter / self.in_elements[0].f_in) ** 2) ** 2  # упрощённо
            dP_local = 0.5 * rho * (v2 - v1) ** 2 * ksi
            # Линейные потери (очень упрощённо)
            K = 0.05
            dP_linear = K * self.length * self.f_in
            self.p_out = self.p_in - dP_local - dP_linear



# Количество входов и выходов. Формула смешения или разделения.
class PipeIntersectionElement(BaseElement):
    """
    Узел пересечения труб: может быть разветвителем (split) или сборщиком (merge).
    """
    def __init__(self, resistances=None, mode='split'):
        """
        resistances: список коэффициентов сопротивления для каждой ветви (float)
        mode: 'split' (разделение потока) или 'merge' (слияние потоков)
        in_elements: список входных элементов (BaseElement)
        """
        super().__init__()
        self.resistances = resistances if resistances is not None else []
        self.mode = mode

    def set_resistances(self, resistances):
        """Установить новые значения сопротивлений для ветвей."""
        self.resistances = resistances

    def get_resistance(self):
        # Например, среднее сопротивление всех ветвей
        if self.resistances:
            return sum(self.resistances) / len(self.resistances)
        return 0.05  # как у трубы по умолчанию

    def update_inputs(self):
        if self.mode == 'split':
            if not self.in_elements or len(self.in_elements) != 1:
                raise ValueError("Для split должен быть ровно один входной элемент.")
            self.t_in = self.in_elements[0].t_out
            self.p_in = self.in_elements[0].p_out
            self.f_in = self.in_elements[0].f_out
        elif self.mode == 'merge':
            if not self.in_elements or len(self.in_elements) < 2:
                raise ValueError("Для merge должно быть два или более входных элемента.")

    def change_f(self):
        if self.mode == 'split':
            f_in = self.f_in
            total_inv_r = sum(1/r for r in self.resistances)
            self.f_out_list = [(1/r)/total_inv_r * f_in for r in self.resistances]
        elif self.mode == 'merge':
            self.f_out = sum(e.f_out for e in self.in_elements)

    def change_t(self):
        if self.mode == 'split':
            self.t_out_list = [self.t_in for _ in self.resistances]
        elif self.mode == 'merge':
            total_flow = sum(e.f_out for e in self.in_elements)
            self.t_out = sum(e.t_out * e.f_out for e in self.in_elements) / (total_flow + 1e-9)

    def change_p(self):
        if self.mode == 'split':
            p_in = self.p_in
            self.p_out_list = [p_in - r*f for r, f in zip(self.resistances, self.f_out_list)]
        elif self.mode == 'merge':
            self.p_out = sum(e.p_out - r*e.f_out for e, r in zip(self.in_elements, self.resistances)) / len(self.in_elements)

    def work(self):
        self.update_inputs()
        self.change_t()
        self.change_p()
        self.change_f()
        # Передаём параметры на выходы
        if self.mode == 'split':
            for idx, elem in enumerate(self.out_elements):
                elem.t_in = self.t_out_list[idx]
                elem.p_in = self.p_out_list[idx]
                elem.f_in = self.f_out_list[idx]
        elif self.mode == 'merge':
            for elem in self.out_elements:
                elem.t_in = self.t_out
                elem.p_in = self.p_out
                elem.f_in = self.f_out


class FilterElement(BaseElement):
    """
    Фильтр: создает дополнительное сопротивление потоку.
    Можно задать степень загрязнения (увеличивает сопротивление).
    """
    def __init__(self, resistance=1.0, clog_factor=1.0, base_resistance = 1.0):
        """
        resistance: базовое гидравлическое сопротивление фильтра
        clog_factor: коэффициент загрязнения (1.0 — чистый, >1.0 — загрязнён)
        """
        super().__init__(resistance=base_resistance)
        self.clog_factor = clog_factor  # 1.0 — чистый, >1.0 — грязный

    def get_resistance(self):
        # Сопротивление фильтра зависит от степени загрязнения
        return self.resistance * self.clog_factor

    def change_p(self):
        # Потери давления на фильтре: dP = R * Q * clog_factor
        self.p_out = self.p_in - self.resistance * self.f_in * self.clog_factor


    def clog(self, factor):
        """
        Засорить фильтр (увеличить сопротивление).
        factor: новый коэффициент загрязнения (>1.0)
        """
        self.clog_factor = factor

    def clean(self):
        """
        Очистить фильтр (вернуть к исходному состоянию).
        """
        self.clog_factor = 1.0


class PumpElement(BaseElement):
    """
    Насос: задаёт напор (разницу давлений), расход определяется схемой.
    """
    def __init__(self, max_pressure=0.5):
        super().__init__()
        self.status = False      # Включён/выключен
        self.power = 0.0         # Мощность (0...1)
        self.max_pressure = max_pressure  # Максимальный напор (например, бар)        # Расход будет рассчитан схемой

    def set_status(self, status: bool):
        self.status = status

    def set_power(self, power: float):
        self.power = max(0.0, min(1.0, power))

    def change_p(self):
        if self.status:
            # p_out = p_in + напор насоса
            self.p_out = (self.p_in if self.p_in is not None else 0.0) + self.max_pressure * self.power
        else:
            self.p_out = self.p_in if self.p_in is not None else 0.0



class MovElement(BaseElement):
    """
    Задвижка/клапан: регулирует расход за счёт изменения сопротивления.
    """
    def __init__(self, in_elements=None, resistance_open=0.05, resistance_closed=1000.0):
        super().__init__(in_elements)
        self.position = 1.0  # 1.0 — полностью открыт, 0.0 — полностью закрыт
        self.resistance_open = resistance_open
        self.resistance_closed = resistance_closed

    @property
    def resistance(self):
        # Сопротивление зависит от положения задвижки
        return self.resistance_open + (self.resistance_closed - self.resistance_open) * (1 - self.position)

    def get_resistance(self):
        return self.resistance

    def set_position(self, position):
        """
        Установить положение задвижки (0.0 — закрыта, 1.0 — открыта)
        """
        self.position = max(0.0, min(1.0, position))

    def change_f(self):
        # Q = (p_in - p_out) / R
        if self.resistance > 0:
            self.f_out = max((self.p_in - self.p_out) / self.resistance, 0.0)
        else:
            self.f_out = 0.0

    def change_p(self):
        # p_out = p_in - Q * R
        self.p_out = self.p_in - self.f_out * self.resistance

    def change_t(self):
        self.t_out = self.t_in


class ValveElement(BaseElement):
    def __init__(self, in_elements=None, resistance_open=0.1, resistance_closed=1000.0):
        super().__init__(in_elements)
        self.opening = 1.0  # 1.0 — полностью открыт, 0.0 — закрыт
        self.resistance_open = resistance_open
        self.resistance_closed = resistance_closed

    @property
    def resistance(self):
        # Сопротивление зависит от открытия
        return self.resistance_open + (self.resistance_closed - self.resistance_open) * (1 - self.opening)

    def get_resistance(self):
        return self.resistance

    def change_f(self):
        # Q = (p_in - p_out) / R
        if self.resistance > 0:
            self.f_out = max((self.p_in - self.p_out) / self.resistance, 0.0)
        else:
            self.f_out = 0.0

    def change_p(self):
        # p_out = p_in - Q * R
        self.p_out = self.p_in - self.f_out * self.resistance


class CapacityElement(BaseElement):
    """
    Ёмкость/резервуар с несколькими входами и выходами, с учётом уровня, температуры и давления.
    Давление в МПа.
    """
    def __init__(self, num_in=1, num_out=1, volume=10.0, tank_area=1.0, in_elements=None):
        super().__init__(in_elements)
        self.num_in = num_in
        self.num_out = num_out
        self.in_elements = [None] * num_in
        self.out_elements = [None] * num_out
        self.volume = volume          # Объём ёмкости, м3
        self.tank_area = tank_area    # Площадь сечения, м2
        self.level = 0.0              # Уровень жидкости, м
        self.t_capacity = 20.0        # Температура в ёмкости, °C
        self.p_capacity = 0.1         # Давление в ёмкости, МПа

    def set_in_element(self, idx, element):
        if 0 <= idx < self.num_in:
            self.in_elements[idx] = element

    def set_out_element(self, idx, element):
        if 0 <= idx < self.num_out:
            self.out_elements[idx] = element

    def set_level(self, level):
        self.level = max(0.0, min(level, self.volume / self.tank_area))

    def set_temperature(self, temperature):
        self.t_capacity = temperature

    def set_pressure(self, pressure):
        self.p_capacity = pressure

    def update_inputs(self):
        # Суммируем расходы всех входов
        self.f_in = sum(e.f_out for e in self.in_elements if e is not None)
        # Температура и давление — средневзвешенные по расходу
        total_flow = self.f_in
        if total_flow > 0:
            self.t_in = sum((e.t_out * e.f_out) for e in self.in_elements if e is not None) / total_flow
            self.p_in = sum((e.p_out * e.f_out) for e in self.in_elements if e is not None) / total_flow
        else:
            self.t_in = self.t_capacity
            self.p_in = self.p_capacity

    def change_f(self):
        # Расход на выходах равномерно делится или задаётся внешне
        if self.num_out > 0:
            self.f_out = self.f_in
            self.f_out_list = [self.f_out / self.num_out] * self.num_out
        else:
            self.f_out = 0.0
            self.f_out_list = []

    def change_t(self):
        # Температура ёмкости изменяется с учётом входных потоков (упрощённо)
        alpha = 0.1  # коэффициент "инерции" ёмкости
        self.t_capacity = (1 - alpha) * self.t_capacity + alpha * self.t_in
        self.t_out_list = [self.t_capacity] * self.num_out

    def change_p(self):
        # Давление ёмкости изменяется с учётом входных потоков (упрощённо)
        beta = 0.1  # коэффициент "инерции" ёмкости
        self.p_capacity = (1 - beta) * self.p_capacity + beta * self.p_in
        self.p_out_list = [self.p_capacity] * self.num_out

    def update_level(self, dt=1.0):
        """
        Обновить уровень в ёмкости за шаг времени dt (сек).
        """
        net_flow = self.f_in - sum(self.f_out_list)
        dV = net_flow * dt  # изменение объёма (м3)
        dH = dV / self.tank_area
        self.level = max(0.0, min(self.level + dH, self.volume / self.tank_area))

    def work(self, dt=1.0):
        self.update_inputs()
        self.change_t()
        self.change_p()
        self.change_f()
        self.update_level(dt)
        # Передаём параметры на выходы
        for idx, elem in enumerate(self.out_elements):
            if elem is not None:
                elem.t_in = self.t_out_list[idx]
                elem.p_in = self.p_out_list[idx]
                elem.f_in = self.f_out_list[idx]


class BoilerElement(BaseElement):
    """
    Водогрейный котёл: изменяет температуру, имеет сопротивление, управляется мощностью.
    """
    def __init__(self, max_power_mw=10.0, min_power_percent=0.2, resistance=0.1):
        super().__init__()
        self._max_power_mw = max_power_mw
        self._min_power_percent = min_power_percent  # Минимальный процент мощности (0...1)
        self._power_percent = 0.0  # Текущий процент мощности (0...1)
        self._status = False
        self._resistance = resistance

    # --- Геттеры и сеттеры ---
    def get_max_power(self):
        return self._max_power_mw

    def get_min_power_percent(self):
        return self._min_power_percent

    def get_power_percent(self):
        return self._power_percent

    def set_power_percent(self, percent):
        # Ограничение: если котёл включён, не ниже минимального процента
        if self._status:
            self._power_percent = max(self._min_power_percent, min(1.0, percent))
        else:
            self._power_percent = 0.0

    def get_status(self):
        return self._status

    def set_status(self, status: bool):
        self._status = status
        if not status:
            self._power_percent = 0.0

    def get_resistance(self):
        return self._resistance

    def set_resistance(self, value):
        self._resistance = value

    # --- Основные методы ---
    def change_t(self):
        # Если котёл включён, увеличиваем температуру на выходе
        if self._status and self.f_in > 0:
            # Q = m * c * dT, где Q — мощность (Вт), m — расход (кг/с), c — теплоёмкость (Дж/кг*К)
            # Для воды: c ≈ 4200 Дж/кг*К, плотность ≈ 1000 кг/м3
            Q = self._max_power_mw * 1e6 * self._power_percent  # Вт
            m = self.f_in * 1000  # м3/с -> кг/с
            dT = Q / (m * 4200) if m > 0 else 0
            self.t_out = self.t_in + dT
        else:
            self.t_out = self.t_in

    def change_p(self):
        # Потери давления на котле
        self.p_out = self.p_in - self._resistance * self.f_in

    def change_f(self):
        self.f_out = self.f_in


class ThermalFluidElement(BaseElement):
    """
    Потребитель тепла (теплообменник, радиатор и т.п.).
    """
    def __init__(self, heat_demand=1.0, resistance=0.1, in_elements=None):
        super().__init__(in_elements)
        self._heat_demand = heat_demand      # МВт
        self._resistance = resistance

    def get_heat_demand(self):
        return self._heat_demand

    def set_heat_demand(self, value):
        self._heat_demand = value

    def get_resistance(self):
        return self._resistance

    def set_resistance(self, value):
        self._resistance = value

    def change_t(self):
        # t_out = t_in - Q / (m * c)
        if self.f_in > 0:
            Q = self._heat_demand * 1e6  # Вт
            m = self.f_in * 1000         # м3/с -> кг/с
            dT = Q / (m * 4200) if m > 0 else 0
            self.t_out = self.t_in - dT
        else:
            self.t_out = self.t_in

    def change_p(self):
        self.p_out = self.p_in - self._resistance * self.f_in

    def change_f(self):
        self.f_out = self.f_in



# 2. Вариант "насос задаёт напор (давление), расход считается по всей схеме"
#
# Это более универсальный и физически корректный подход.
# Насос задаёт напор (разницу давлений), а расход через каждый элемент (в том числе через регулирующий клапан) рассчитывается по формуле: [ Q = /frac{\Delta P}{R} ] где ( \Delta P ) — разность давлений на концах элемента, ( R ) — гидравлическое сопротивление.
