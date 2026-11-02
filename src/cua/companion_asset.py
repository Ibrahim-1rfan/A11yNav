"""The companion's look, in one place so the design can be swapped. Soft, tail-less teal pointer."""
SVG = """<svg width="22" height="22" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M5 3.5 L5 18 L9.6 14 L17 13.6 Z"
        fill="#1D9E75" stroke="#ffffff" stroke-width="2.4" stroke-linejoin="round"/>
</svg>"""
SIZE = 22                      # rendered px, about 75% of the system cursor
TIP = (5 / 24 * SIZE, 3.5 / 24 * SIZE)  # the pointer's tip inside the 22 px box; squish shrinks toward it
