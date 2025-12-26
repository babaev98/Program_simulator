from BaseElement import *
from pymodbus.client import ModbusTcpClient
from enum import Enum, auto
import json
from collections import OrderedDict

class ModbusAddressMapGenerator:
    def __init__(self, start_coil=0, start_discrete_input=0,
                 start_hr=0, start_ir=0):
        self.next_coil = start_coil
        self.next_di = start_discrete_input
        self.next_hr = start_hr
        self.next_ir = start_ir

        # Итоговая карта: для удобства дальше
        self.map = OrderedDict()  # key: "ElementType[index].field"

    def generate_for_scheme(self, scheme:ProcessScheme):
        """
        scheme.elements_dict: {index: element}
        """
        for idx, elem in scheme.elements_dict.items():
            # если у элемента нет modbus-модели — пропускаем
            if not hasattr(elem, "modbus") or elem.modbus is None:
                continue

            elem_type = type(elem).__name__
            base_name = f"{elem_type}[{idx}]"

            # Входы
            for field, meta in elem.modbus.inputs.items():
                full_name = f"{base_name}.{field}"
                addr, area = self._allocate_address(meta)
                self.map[full_name] = {
                    "direction": "in",
                    "area": area,
                    "address": addr,
                    "type": meta["type"],
                    "scale": meta.get("scale", 1.0),
                }

            # Выходы
            for field, meta in elem.modbus.outputs.items():
                full_name = f"{base_name}.{field}"
                addr, area = self._allocate_address(meta)
                self.map[full_name] = {
                    "direction": "out",
                    "area": area,
                    "address": addr,
                    "type": meta["type"],
                    "scale": meta.get("scale", 1.0),
                }

        return self.map

    def _allocate_address(self, meta):
        t = meta["type"]
        w = meta.get("width", 1)

        if t == "coil":
            addr = self.next_coil
            self.next_coil += w
            return addr, "coil"

        if t == "di":  # discrete input
            addr = self.next_di
            self.next_di += w
            return addr, "di"

        if t == "hr":  # holding register
            addr = self.next_hr
            self.next_hr += w
            return addr, "hr"

        if t == "ir":  # input register
            addr = self.next_ir
            self.next_ir += w
            return addr, "ir"

        # по умолчанию — holding
        addr = self.next_hr
        self.next_hr += w
        return addr, "hr"

    def save_to_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.map, f, ensure_ascii=False, indent=2)

    def save_to_csv(self, path):
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["Name", "Direction", "Area", "Address", "Type", "Scale"])
            for name, meta in self.map.items():
                w.writerow([
                    name,
                    meta["direction"],
                    meta["area"],
                    meta["address"],
                    meta["type"],
                    meta.get("scale", 1.0),
                ])


class PlcSignalDirection(Enum):
    INPUT = auto()   # из ПЛК в модель
    OUTPUT = auto()  # из модели в ПЛК

class PlcSignalType(Enum):
    COIL = auto()
    DISCRETE_INPUT = auto()
    HOLDING_REGISTER = auto()
    INPUT_REGISTER = auto()

class PlcSignal:
    def __init__(self, name, address, sig_type:PlcSignalType,
                 direction:PlcSignalDirection,
                 scale=1.0, offset=0.0):
        self.name = name
        self.address = address
        self.sig_type = sig_type
        self.direction = direction
        self.scale = scale
        self.offset = offset
        self.value = None  # последнее считанное / отправленное значение

    def from_raw(self, raw):
        # масштабирование из регистра в физ. значение
        return raw * self.scale + self.offset

    def to_raw(self, value):
        # из физ. значения в регистр
        return int(round((value - self.offset) / self.scale))


class ModbusClientManager:
    def __init__(self, host, port=502):
        self.client = ModbusTcpClient(host, port=port)
        self.client.connect()


class PlcBinding:
    """
    Связывает логический элемент с сигналом ПЛК.
    """
    def __init__(self, element, attr_name:str, signal:PlcSignal):
        self.element = element        # логический элемент (PumpElement, BoilerElement, Sensor и т.п.)
        self.attr_name = attr_name
        self.signal = signal