class Unit:
    DEGREES_C = 'C'
    DEGREES_F = 'F'

class W1ThermSensor:
    def __init__(self, sensor_id="default_sensor"):
        self.sensor_id = sensor_id
        self.temperature = 23.0

    def get_temperature(self, sensor_units=Unit.DEGREES_C):
        if sensor_units == Unit.DEGREES_C:
            return self.temperature
        elif sensor_units == Unit.DEGREES_F:
            return (self.temperature * 9/5) + 32
        else:
            raise ValueError(f"Unsupported sensor_units: {sensor_units}")

    def set_temperature(self, temperature):
        self.temperature = temperature

    def __call__(self):
        return self

