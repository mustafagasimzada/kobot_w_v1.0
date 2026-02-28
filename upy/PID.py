import utime

class PID:
    def __init__(self, kp, ki, kd, setpoint=0.0000 , output_limits=(None, None)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self._min_out, self._max_out = output_limits

        self._last_error = 0
        self._integral = 0
        self._last_time = utime.ticks_ms()

    def update(self, measurement):
        # Geçen süreyi hesapla (ms -> saniye)
        now = utime.ticks_ms()
        dt = utime.ticks_diff(now, self._last_time) / 1000.0
        if dt <= 0: return 0  # Hatalı zamanlama kontrolü

        # Hata hesaplama
        error = self.setpoint - measurement

        # P (Proportional) terimi
        p_term = self.kp * error

        # I (Integral) terimi + Anti-Windup (Limitler varsa integrali durdur)
        self._integral += error * dt
        i_term = self.ki * self._integral
        
        if self._min_out is not None and self._max_out is not None:
            i_term = max(self._min_out, min(i_term, self._max_out))

        # D (Derivative) terimi
        d_term = self.kd * (error - self._last_error) / dt

        # Toplam çıkış
        output = p_term + i_term + d_term

        # Çıkış limitlerini uygula (PWM doyumu gibi durumlar için)
        if self._min_out is not None and self._max_out is not None:
            output = max(self._min_out, min(output, self._max_out))

        # Durumları güncelle
        self._last_error = error
        self._last_time = now

        return output

    def reset(self):
        self._integral = 0
        self._last_error = 0
        self._last_time = utime.ticks_ms()