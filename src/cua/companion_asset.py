"""The companion's look, in one place so the design can be swapped. Soft, tail-less teal pointer, no outline."""
SVG = """<svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M5 3.5 L5 18 L9.6 14 L17 13.6 Z" fill="#1D9E75" stroke="#1D9E75" stroke-width="2.4" stroke-linejoin="round"/>
</svg>"""
SIZE = 18                      # rendered px, a little smaller than the system cursor
TIP = (5 / 24 * SIZE, 3.5 / 24 * SIZE)  # the pointer's tip inside the box; squish shrinks toward it
