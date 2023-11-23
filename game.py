import select


class _Getch:
    """Gets a single character from standard input.  Does not echo to the
screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            try:
                self.impl = _GetchUnix()
            except:
                self.impl = _GetchMacCarbon()

    def __call__(self, wait_time_secs): return self.impl(wait_time_secs)


class _GetchUnix:
    def __init__(self):
        import tty, sys, termios

    def __call__(self, wait_time_secs):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        terminate = False
        try:
            tty.setraw(sys.stdin.fileno())
            readable, _, _ = select.select([sys.stdin], [], [], wait_time_secs)
            ch = None
            if len(readable) > 0 and readable[0] is sys.stdin:
                ch = sys.stdin.read(1)
                if ord(ch) == 3:
                    terminate = True
            
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        if terminate:
            print("Interrupted")
            exit(1)
        return ch


class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self, wait_time_secs):
        import msvcrt
        return msvcrt.getch()


class _GetchMacCarbon:
    """
    A function which returns the current ASCII key that is down;
    if no ASCII key is down, the null string is returned.  The
    page http://www.mactech.com/macintosh-c/chap02-1.html was
    very helpful in figuring out how to do this.
    """
    def __init__(self):
        import Carbon

    def __call__(self, wait_time_secs):
        import Carbon
        if Carbon.Evt.EventAvail(0x0008)[0]==0: # 0x0008 is the keyDownMask
            return ''
        else:
            #
            # The event contains the following info:
            # (what,msg,when,where,mod)=Carbon.Evt.GetNextEvent(0x0008)[1]
            #
            # The message (msg) contains the ASCII char which is
            # extracted with the 0x000000FF charCodeMask; this
            # number is converted to an ASCII character with chr() and
            # returned
            #
            (what,msg,when,where,mod)=Carbon.Evt.GetNextEvent(0x0008)[1]
            return chr(msg & 0x000000FF)



class World:

    def __init__(self, width, height) -> None:
        self.width = width
        self.height = height
        self.objects = []

    def add_object(self, object):
        self.objects.append(object)
        
    def draw(self, screen):
        for obj in self.objects:
            obj.draw(screen)
        pass

class WObject: 

    def __init__(self, width, height, pos, world=None, color=None, character=None) -> None:
        self.width = width
        self.height = height
        self.pos = pos
        self.world = world
        self.color = color or (1, 1, 1)
        self.character = character or "*"

    def move(self, dx, dy):
        x, y = self.pos
        self.pos = (x + dx, y + dy)

    def place(self, x, y):
        self.pos = (x, y)

    def collides_with(self, other):
        pass

    def draw(self, screen):
        pass


class Screen:

    def __init__(self, width, height, color=(0, 0, 0)) -> None:
        self._lines_shown = 0
        self.color = color
        self.width = width
        self.height = height
        self.D_PIXEL = (None, self.color)
        self.pixels = [[self.D_PIXEL] * self.height for _ in range(self.width)]
        self.bgd_xter = "®"

        self.errors = []

    def clear(self, color=None):
        if color is None:
            color = self.color
        self.pixels = [[self.D_PIXEL] * self.height for _ in range(self.width)]
    
    def set_pixel(self, x, y, pixel): # a pixel is a (xter, color) tuple
        # do checks here that way if we draw outside the screen it's simply ignored
        # maybe add an errror buffer that gets shown after the screen 
        # so we write errors there!?
        if y < 0 or x < 0 or y > len(self.pixels) or x > len(self.pixels[0]):
            self.errors.append(f"Screen overflow: x = {x}, y = {y}")
            return
        self.pixels[y][x] = pixel


    def _color_text(self, color, text):
        return f"{color}{text}"
    
    def _bgd(self, text):
        return self._color_text("\033[1;34m", text)
    
    def _fgd(self, text):
        return self._color_text("\033[1;31m", text)
    
    def _draw_pixel(self, pixel):
        xter, color = pixel
        r,g,b = color
        return self._bgd(self.bgd_xter) if xter is None else self._fgd(xter)
        
    def show(self, grey_scale=True):
        print("\033[2J\033[H") # clear screen and move cussor to the top (0, 0) of termainal
        # print pixels to screen and flush
        # demo to remove
        edg = self._bgd("│")
        tlgd = self._bgd("┌")
        trgd = self._bgd("┐")
        blgd = self._bgd("└")
        brgd = self._bgd("┘")
        yedge = self._bgd("─")
        bar = " ".join([yedge] * len(self.pixels[0]))
        top = tlgd + bar + trgd + "\n"
        bottom = "\n" + blgd + bar + brgd
        page = "\n".join([ edg + " ".join([self._draw_pixel(e) for e in row]) + edg for row in self.pixels])
        page = top + page + bottom
        print(page, flush=True)
    


class Controller:

       
    def __init__(self, w=20, h=20) -> None:
        self.w = w
        self.h = h
        self.screen = Screen(self.w, self.h)
        self.world = World(self.w, self.h)
        self.exit_signal = "q"
        self.getch = _Getch()
        pos = (0, 0)
        self.actor = Snake(pos, world=self.world, length=9, character="▀")
        self.world.add_object(self.actor)

        food = Food((10, 10), character="∆")
        self.world.add_object(food)

        self._input_buffer = []
        self._MAX_INPUT_BUFFER = 10 # every frame the oldest input is removed

        self.errors = {}

    def get_input(self):
        for i in range(len(self._input_buffer)):
            ch = self._input_buffer.pop(0)
            if ch is not None:
                return ch
        return None
    
    def _show_error(self):
        print()
        for name, error in self.errors.items():
            print(name, ": ", error)
        print(flush=True)

    def _clear_error(self, name):
        if name in self.errors:
            del self.errors[name]

    def _add_error(self, error, name):
        self.errors[name] = [error]

    def _get_errors(self):
        self._add_error(self.screen.errors, "screen")

    def _move_actor(self):
        self.actor.move()


    def update(self):
        ch = self.get_input()
        if ch is not None:
            if ch == "w":
                self.actor.direction = (0, -1)
            if ch == "a":
                self.actor.direction = (-1, 0)
            if ch == "d":
                self.actor.direction = (1, 0)
            if ch == "s":
                self.actor.direction = (0, 1)
        self.actor.move()
        self.screen.clear()
        self.world.draw(self.screen)

    def start(self):
        self.screen.show()

        while True:
            self.update()
            self.screen.show()
            self._get_errors()
            self._show_error()
            self._buffer_input()
            if self._received_exit_signal():
                break
    
    def set_exit_signal(self, signal: str):
        self.exit_signal = signal

    def _received_exit_signal(self):
        # check input buffer for exit signal
        for i in range(len(self._input_buffer) - 1, -1, -1):
            if self._input_buffer[i] == self.exit_signal:
                return True
        return False
        
    def _buffer_input(self):
        ch = self.getch(0.5)
        if len(self._input_buffer) > self._MAX_INPUT_BUFFER:
            self._input_buffer.pop(0) # clear buffer for old commands that haven't been used
        
        if ch is not None: # if no commands don't added to buffer
            self._input_buffer.append(ch)
        self._add_error(self._input_buffer, "input buffer")
        return ch

    
    def sleep(self, seconds):
        # use time diffencece from start of loop to current point in loop instead
        import time
        seconds *= 10**9
        start_time = time.time_ns()
        while True:
            now = time.time_ns()
            if now - start_time >= seconds:
                break


class Snake(WObject):

    def __init__(self, pos, world=None, color=None, length=1, direction=(1, 0), speed=1, character=None) -> None:
        super().__init__(1, 1, pos, world, color, character)
        self.body = self._create_snake(pos, length) # add directions later
        self.direction = direction
        self.speed = speed

    def translate(self, dx, dy):
        for i in range(len(self.body) - 1, 0, -1):
            self.body[i] = self.body[i - 1]
        self.body[0] = self._move(self.body[0], dx, dy, self.world.width, self.world.height)
        self.pos = self.body[0]

    def _move(self, pos, dx, dy, w, h):
        x, y = pos
        x += dx
        y += dy
        return x % w, y % h
    
    def move(self):
        dx, dy = self.direction
        dx *= self.speed
        dy *= self.speed
        self.translate(dx, dy)
    
    def draw(self, screen):
        for pos in self.body:
            screen.set_pixel(pos[0], pos[1], (self.character, (1, 1, 1)) )

    def _create_snake(self, start, length):
        x, y = start
        snake = [(0, 0)] * length
        for i in range(length):
            snake[i] = (x, y + i)

        return snake

class Food(WObject):

    def __init__(self, pos, world=None, color=None, character=None) -> None:
        super().__init__(1, 1, pos, world, color, character)
    
    def draw(self, screen):
        screen.set_pixel(self.pos[0], self.pos[1], (self.character, (1, 1, 1)))

def main():

    controller = Controller()
    controller.start()


if __name__ == "__main__":
    main()
