from machine import Pin, ADC

class Battery:
    """
    Pil voltajını ölçmek için bağımsız modül.
    """
    def __init__(self, battery_pin, R1=100.0, R2=47.0, ref_voltage=3.3):
        self.battery_adc = ADC(Pin(battery_pin))
        self.ratio = (R1 + R2) / R2
        self.ref_voltage = ref_voltage
        self.current_voltage = 0.0

    def get_voltage(self, samples=10):
        """
        ADC'den okuma yapar ve voltaj değerini döndürür.
        'samples' parametresi ile kaç okumanın ortalamasının alınacağı belirlenir.
        """
        raw_sum = 0
        for _ in range(samples):
            raw_sum += self.battery_adc.read_u16()
        
        avg_raw = raw_sum / samples
        
        # Voltaj hesaplama
        self.current_voltage = (avg_raw / 65535) * self.ref_voltage * self.ratio
        return self.current_voltage

    def get_percentage(self, full_voltage=12.6, empty_voltage=10.5):
        """
        Voltajı yüzdeye çevirir (Örnek: 3S LiPo için varsayılan değerler).
        """
        v = self.get_voltage()
        percentage = ((v - empty_voltage) / (full_voltage - empty_voltage)) * 100
        return max(0, min(100, percentage)) # 0 ile 100 arasına sınırla