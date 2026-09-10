"""Value-crossing feedback, independent of wall time and animation scheduling."""
import math

# Ten short complete thoughts and ten affectionate endings per mood. All 100
# combinations are short enough for the existing single-line bubble.
_THOUGHTS = {
    'mild': ('肚肚有点空', '想尝一口鱼', '有点想吃啦', '小肚子咕噜', '想要小点心', '有一点点饿', '饭香在哪里', '小鱼来一口', '想垫垫肚子', '点心时间到'),
    'severe': ('好饿好饿呀', '快给点吃的', '肚肚叫不停', '急需小鱼干', '真的好想吃', '快开饭好嘛', '小猫等饭急', '饿得直跺爪', '饭饭快来呀', '快救救肚肚'),
    'critical': ('快饿扁了呀', '不要我了吗', '饿到没力啦', '救救小猫呀', '一口也好呀', '快饿晕了喵', '饭饭别走呀', '肚肚撑不住', '求求喂一口', '饿死小猫啦'),
    'full': ('嗝儿好饱呀', '肚肚圆滚滚', '吃饱好幸福', '小猫好满足', '饭饭太香啦', '饱饱暖呼呼', '谢谢这顿饭', '满足到眯眼', '今天好幸福', '小鱼装满啦'),
}
_ENDINGS = ('，喵～', '，嘿嘿', '，主人呀', '，咪呜', '，喵喵', '，蹭蹭你', '，小声喵', '，眨眨眼', '，贴贴呀', '，呜咪～')
CORPUS = {mood: tuple(a + b for a in thoughts for b in _ENDINGS) for mood, thoughts in _THOUGHTS.items()}


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
