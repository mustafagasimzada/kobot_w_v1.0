# encoder_portable.py

# Encoder Support: this version should be portable between MicroPython platforms
# Thanks to Evan Widloski for the adaptation to use the machine module

# Copyright (c) 2017-2022 Peter Hinch
# Released under the MIT License (MIT) - see LICENSE file

import utime
from machine import Pin

class Encoder:
    def __init__(self, pin_x, pin_y, scale=1):
        self.scale = scale
        self.forward = True
        self.pin_x = pin_x
        self.pin_y = pin_y
        self._x = pin_x()
        self._y = pin_y()
        self._pos = 0
        
        # Hız takibi için gerekli olan başlangıç değerleri
        self.last_pos = 0
        self.last_time = utime.ticks_ms()

        try:
            self.x_interrupt = pin_x.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.x_callback, hard=True)
            self.y_interrupt = pin_y.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.y_callback, hard=True)
        except TypeError:
            self.x_interrupt = pin_x.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.x_callback)
            self.y_interrupt = pin_y.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.y_callback)

    def x_callback(self, pin_x):
        if (x := pin_x()) != self._x:  # Reject short pulses
            self._x = x
            self.forward = x ^ self.pin_y()
            self._pos += 1 if self.forward else -1

    def y_callback(self, pin_y):
        if (y := pin_y()) != self._y:
            self._y = y
            self.forward = y ^ self.pin_x() ^ 1
            self._pos += 1 if self.forward else -1

    def position(self, value=None):
        if value is not None:
            self._pos = round(value / self.scale)  # Improvement provided by @IhorNehrutsa
        return self._pos * self.scale

    def value(self, value=None):
        if value is not None:
            self._pos = value
        return self._pos

    def velocity(self):
        """
        Anlık hızı pals/saniye cinsinden döndürür.
        """
        current_time = utime.ticks_ms()
        current_pos = self._pos
        
        # Zaman farkını saniye cinsinden hesapla (ms -> s)
        dt = utime.ticks_diff(current_time, self.last_time) / 1000.0
        
        if dt > 0:
            # Hız = Yer değiştirme / Zaman
            vel = (current_pos - self.last_pos) / dt
            
            # Değerleri bir sonraki çağrı için güncelle
            self.last_pos = current_pos
            self.last_time = current_time
            
            return vel * self.scale
        
        
        else:
            return 0.0
        
    def meters_per_second(self):
        """
        Anlık hızı m/s cinsinden döndürür.
        Hesaplama: 600 pals = 1 tam tur (0.12566 metre)
        """
        # Önce pals/saniye hızını al
        v_pals = self.velocity()
        
        # Sabitler
        pulses_per_wheel_rev = 600  # Senin verdiğin güncel değer
        wheel_diameter = 0.04       # 4 cm -> metre
        pi = 3.14159
        
        # Tekerlek çevresi
        wheel_circumference = pi * wheel_diameter 
        
        # Metre/Saniye hesabı
        v_meters = (v_pals / pulses_per_wheel_rev) * wheel_circumference
        
        return v_meters   