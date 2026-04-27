import matplotlib.pyplot as plt
from investment_analyser.portfolio import *

p = Portfolio()
p.plot_securities()

# This will block execution and keep all figures open until manually closed
plt.show(block=True)
