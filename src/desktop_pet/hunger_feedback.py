"""Value-crossing feedback, independent of wall time and animation scheduling."""
import math

from .hunger_phrases import CORPUS


class HungerFeedback:
    def __init__(self):
        self.previous = None
        self.critical = False

    def update(self, units):
        units = max(0, min(100000, int(units)))
        previous, self.previous = self.previous, units
        self.critical = units < 1000
        if previous is None:
            return 'critical' if self.critical else None
        if units == 100000 and previous < units:
            return 'full'
        if units >= previous:
            return None
        if units < 1000:
            return 'critical' if previous >= 1000 else None
        # Strict stage entry at <10%; exactly 10% is still mild.
        crossed = previous >= 10000 > units
        crossed |= any(units <= threshold < previous for threshold in range(2000, 20001, 2000))
        return ('severe' if units < 10000 else 'mild') if crossed else None


def bar_color(units):
    ratio = max(0, min(100000, units)) / 100000
    return tuple(round(a + (b - a) * ratio) for a, b in zip((235, 75, 75), (75, 196, 107)))


def motion(mood, elapsed):
    """Logical-pixel shake and bubble scale; bounded at all timestamps."""
    if mood == 'full':
        t = max(0, elapsed)
        return 0, 0, max(.25, 1 - math.exp(-8*t) * math.cos(16*t))
    amplitude, frequency = {'mild': (1.5, 3), 'severe': (3, 6), 'critical': (5, 10)}[mood]
    return amplitude * math.sin(elapsed * frequency * math.tau), amplitude * .4 * math.cos(elapsed * frequency * math.tau), 1
