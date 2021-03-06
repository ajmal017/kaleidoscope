# pylint: disable=E1101
import re
from datetime import datetime

from kaleidoscope.globals import OrderAction
from kaleidoscope.options.option import Option
from kaleidoscope.options.option_query import OptionQuery


class OptionStrategy(object):
    """
    This class holds all constructed option strategies created from OptionStrategies
    class' static methods. The provided convenience methods will return a single strategy
    that matches the method requirements.
    """

    def __init__(self, chains, original_chains, name=None):
        """
        This class holds an instance of an option strategy and it's
        components and provides methods to manipulate the option legs
        contained within.

        :params: chains: Dataframe containing shifted columns representing an option leg
        """
        self.chains = chains
        self._chains = original_chains.drop('strike_key', axis=1)
        self.name = name

        if self.chains is not None:
            self.underlying_symbol = chains['underlying_symbol'][0]

        # attributes to be filled when 'nearest' methods are used
        self.legs = None
        self.symbols = None
        self.expirations = None
        self.strikes = None
        self.option_types = None

        self.mark = None
        self.max_strike_width = None

    def calc_mark(self):
        """
        Calculate the mark value of this option strategy based on current prices
        :return: None
        """
        if self.legs is not None:
            return sum(leg['contract'].mark * leg['quantity'] for leg in self.legs)

    def _map(self, strat_sym):
        """
        Takes an array or parsed option spread symbol and create option legs
        as per symbol's arrangement

        :param strat_sym: Array containing the components of an option spread's symbol
        :return:
        """

        trimmed_sym = strat_sym.replace(".", "")
        parsed = re.findall('\W+|\w+', trimmed_sym)

        strat_legs = list()
        symbols = list()
        exps = list()
        strikes = list()

        # default mapping for each option symbol
        quantity = 1
        side = OrderAction.BUY

        for piece in parsed:
            if piece == "+":
                side = OrderAction.BUY
                continue
            elif piece == "-":
                side = OrderAction.SELL
                continue
            else:
                try:
                    quantity = int(piece)
                    continue
                except ValueError:
                    pass

            if len(piece) >= 18:
                # this is an option symbol, get option info
                sym_info = self._chains[self._chains['symbol'] == piece].to_dict(orient='records')[0]
                # convert pandas datetime
                expiration = sym_info['expiration'].date().strftime("%Y-%m-%d")

                option = Option(sym_info)

                if piece not in symbols:
                    symbols.append(piece)

                if expiration not in exps:
                    exps.append(expiration)

                if sym_info['strike'] not in strikes:
                    strikes.append(sym_info['strike'])

                strat_legs.append({'contract': option, 'quantity': quantity*side.value})

                quantity = 1
                side = OrderAction.BUY

        self.symbols = symbols
        self.expirations = exps
        self.strikes = strikes

        return strat_legs

    def _max_strike_width(self):
        """
        Calculate the max strike widths stored in strikes list
        :return: Max strike width
        """
        length = len(self.strikes)
        if length == 1:
            return 0
        elif length == 2:
            return abs(self.strikes[1] - self.strikes[0])
        elif length == 3:
            return max(abs(self.strikes[1] - self.strikes[0]),
                       abs(self.strikes[2] - self.strikes[1]))
        elif length == 4:
            return max(abs(self.strikes[1] - self.strikes[0]),
                       abs(self.strikes[3] - self.strikes[2]))
        else:
            raise ValueError("invalid amounts of strikes in option strategy")

    def nearest_mark(self, mark, tie='roundup'):
        """
        Returns the object itself with the legs attribute containing the option legs
        that matches the mark value and 'expiration', 'strikes' and 'symbol' attributes
        assigned.

        :param mark: Mark value to match option spread with
        :param tie: how to handle multiple matches for mark value
        :return: Self
        """
        spread = OptionQuery(self.chains).closest('mark', mark).fetch()

        if len(spread) != 1:
            max_mark_idx = spread['mark'].idxmax()
            min_mark_idx = spread['mark'].idxmin()

            if tie == 'roundup':
                self.legs = self._map(spread['symbol'][max_mark_idx])
                self.mark = spread['mark'][max_mark_idx]
            else:
                self.legs = self._map(spread['symbol'][min_mark_idx])
                self.mark = spread['mark'][min_mark_idx]
        else:
            self.legs = self._map(spread['symbol'][0])
            self.mark = spread['mark'][0]

        self.max_strike_width = self._max_strike_width()

        return self

    def nearest_delta(self, price):
        """

        :param price:
        :return:
        """
        pass

    def filter(self, func, **params):
        """

        :param func:
        :param params:
        :return:
        """
        pass

    def __str__(self):
        if self.legs is None:
            return f"{self.name}s"
        else:
            n = self.name.upper()
            s = self.underlying_symbol

            exps = self.expirations
            p_e = [datetime.strptime(exp, "%Y-%m-%d") for exp in exps]
            e = "".join('%s/' % p.strftime('%d %b %y').upper() for p in p_e)[0: -1]

            sts = self.strikes
            st = "".join('%s/' % '{0:g}'.format(st) for st in sts)[0: -1]

            return f"{n} {s} {e} {st}"
