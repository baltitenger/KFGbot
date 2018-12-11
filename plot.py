from util import *
from subprocess import run

class Plot():
  controls = {
    '\U00002795': lambda xcenter, ycenter, xspan, yspan:
      (xcenter - xspan / 2, xcenter + xspan / 2, ycenter - yspan / 2, ycenter + yspan / 2),
    '\U00002796': lambda xcenter, ycenter, xspan, yspan:
      (xcenter - xspan * 2, xcenter + xspan * 2, ycenter - yspan * 2, ycenter + yspan * 2),
    '\U000027A1': lambda xcenter, ycenter, xspan, yspan:
      (xcenter, xcenter + xspan * 2, ycenter - yspan, ycenter + yspan),
    '\U00002B05': lambda xcenter, ycenter, xspan, yspan:
      (xcenter - xspan * 2, xcenter, ycenter - yspan, ycenter + yspan),
    '\U00002B06': lambda xcenter, ycenter, xspan, yspan:
      (xcenter - xspan, xcenter + xspan, ycenter, ycenter + yspan * 2),
    '\U00002B07': lambda xcenter, ycenter, xspan, yspan:
      (xcenter - xspan, xcenter + xspan, ycenter - yspan * 2, ycenter),
    '\U0001F1F4': lambda xcenter, ycenter, xspan, yspan:
      (-5, 5, -5, 5),
    }

  options = 'set term png crop size 1000, 1000; set size ratio -1; set samples 2000; set grid; set zeroaxis; unset border; set xrange [{xstart}:{xend}]; set yrange [{ystart}:{yend}]; set xtics axis {xrate}; set ytics axis {yrate}; plot {function}'

  def genPlot(function, xstart=-5, xend=5, ystart=-5, yend=5) -> discord.File or str:
    output = run(['gnuplot', '-e', Plot.options.format(xstart=xstart, xend=xend, ystart=ystart, yend=yend, xrate=(xend - xstart) / 10, yrate=(yend - ystart) / 10, function=function)], capture_output=True)
    if output.returncode == 0:
      return discord.File(output.stdout, filename="plot.png")
    else:
      return output.stderr.decode('utf-8')

  async def plot(channel, args): # can throw exception, unhandled for now
    """plot [ranges] function
    Reply with an image of the plot of [function]. See the documentation of gnuplot for additional info."""
    await channel.trigger_typing()
    function = ''.join(args)
    plot = Plot.genPlot(function)
    if type(plot) == discord.File:
      message = await channel.send("Plot of `{}`:".format(function), file=plot)
      for i in Plot.controls.keys():
        await message.add_reaction(i)
    else:
      await Util.sendError(channel, plot)

  async def updatePlot(reaction, user):
    message = reaction.message
    channel = message.channel
    if message.author != client.user or user == client.user:
      return
    split = message.content.split('`')
    function = split[1]
    if len(split) > 3: # there is a range
      xstart, xend, ystart, yend = split[3].split(', ')
      xstart = float(xstart)
      xend = float(xend)
      ystart = float(ystart)
      yend = float(yend)
    else:
      xstart, xend, ystart, yend = (-5.0, 5.0, -5.0, 5.0)
    xcenter = (xstart + xend) / 2
    ycenter = (ystart + yend) / 2
    xspan = (xend - xstart) / 2
    yspan = (yend - ystart) / 2
    xstart, xend, ystart, yend = Plot.controls[reaction.emoji](xcenter, ycenter, xspan, yspan)
    plot = Plot.genPlot(function, xstart, xend, ystart, yend)
    await message.delete()
    message = await channel.send("Plot of `{}`: [`{}, {}, {}, {}`]".format(function, xstart, xend, ystart, yend), file=plot)
    for i in Plot.controls.keys():
      await message.add_reaction(i)

