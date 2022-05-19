from credmark.cmf.model import Model
from credmark.dto import DTO

from credmark.cmf.types import Contract, Token, Price

import numpy as np
import pandas as pd
from pyrsistent import b

from models.credmark.algorithms.value_at_risk.dto import UniswapPoolVaRInput

from models.credmark.algorithms.value_at_risk.risk_method import calc_var


@Model.describe(slug="finance.dex-lp-var",
                version="1.0",
                display_name="VaR for liquidity provider to Pool with IL adjustment to portfolio",
                description="Working for UniV2, V3 and Sushiswap pools",
                input=UniswapPoolVaRInput,
                output=dict)
class UniswapPoolVaR(Model):
    """
    This model takes
    """

    def run(self, input: UniswapPoolVaRInput) -> dict:
        pool = input.pool

        # get token and balances
        token0 = Token(address=pool.functions.token0().call())
        token1 = Token(address=pool.functions.token1().call())
        bal0 = token0.scaled(token0.functions.balanceOf(pool.address).call())
        bal1 = token1.scaled(token1.functions.balanceOf(pool.address).call())

        # current price
        current_ratio = bal1 / bal0

        token0_price = self.context.run_model(input.price_model, input=token0)
        token1_price = self.context.run_model(input.price_model, input=token1)

        token0_historical_price = (self.context.historical
                                   .run_model_historical(
                                       model_slug=input.price_model,
                                       model_input=token0,
                                       window=input.window,
                                       model_return_type=Price)
                                   .to_dataframe(fields=[('price', lambda p:p.price)])
                                   .sort_values('blockNumber', ascending=False))

        token1_historical_price = (self.context.historical
                                   .run_model_historical(
                                       model_slug=input.price_model,
                                       model_input=token1,
                                       window=input.window,
                                       model_return_type=Price)
                                   .to_dataframe(fields=[('price', lambda p:p.price)])
                                   .sort_values('blockNumber', ascending=False))

        df = pd.DataFrame({
                'TOKEN0/USD': token0_historical_price.price.to_numpy(),
                'TOKEN1/USD': token1_historical_price.price.to_numpy(),
                })

        df.loc[:, 'ratio'] = df['TOKEN0/USD'] / df['TOKEN1/USD']
        ratio_change = df.ratio[:-input.interval].to_numpy() /df.ratio[input.interval:].to_numpy()
        _token0_change = df['TOKEN0/USD'][:-input.interval].to_numpy() / df['TOKEN0/USD'][input.interval:].to_numpy()
        token1_change = df['TOKEN1/USD'][:-input.interval].to_numpy() / df['TOKEN1/USD'][input.interval:].to_numpy()

        # Assume we hold a set of tokens on time 0, we could become a LP provider or do nothing.
        # Impermanent loss is the loss relative to the holding's value on time 1 of the do-nothing case.
        # While the value of the holding on time 1 will have PnL relative to time 0.
        # This goes to the portfolio_pnl_vector.

        # For portfolio PnL vector, we need to match either
        # ratio = Token1 / Token0 with Token0's price change, or
        # ratio = Token0 / Token1 with Token1's price change.
        portfolio_pnl_vector = (1 + ratio_change) / 2 * token1_change - 1

        # Impermenant loss
        # Note:
        # If we change the order for getting the ratio,
        # impermenant_loss_vector_v2/v3 will be very close (invariant for the order)
        # i.e. For V2
        # np.allclose(
        #   2*np.sqrt(ratio_change)/(1+ratio_change)-1,
        #   2*np.sqrt(1/ratio_change)/(1+1/ratio_change)-1
        # )
        impermenant_loss_type = 'V2'
        impermenant_loss_vector_v2 = 2*np.sqrt(ratio_change)/(1+ratio_change) - 1

        impermenant_loss_type = 'V3'
        impermenant_loss_vector_v3 = ((2*np.sqrt(ratio_change) -1 - ratio_change) /
                                   (1 + ratio_change - np.sqrt(1-input.lower_range) -
                                   ratio_change * np.sqrt(1 / (1 + input.uppper_range)) ))

        # IL check
        # import matplotlib.pyplot as plt
        # plt.scatter(1 / ratio_change - 1, impermenant_loss_vector_v2); plt.show()
        # plt.scatter(1 / ratio_change - 1, impermenant_loss_vector_v3); plt.show()
        # Or,
        # plt.scatter(ratio_change - 1, impermenant_loss_vector_v2); plt.show()
        # plt.scatter(ratio_change - 1, impermenant_loss_vector_v3); plt.show()

        # Count in both portfolio PnL and IL for the total Pnl vector
        total_pnl_vector_v2 = (1 + portfolio_pnl_vector) * (1 + impermenant_loss_vector_v2) - 1
        total_pnl_vector_v3 = (1 + portfolio_pnl_vector) * (1 + impermenant_loss_vector_v3) - 1

        var_output = {}
        for conf in input.confidences:
            var_output[conf] = calc_var(total_pnl_vector_v3, conf)

        # For V3, as existing assumptions, we cap the loss at -100%.
        if impermenant_loss_type == 'V3':
            var_output = {k:(v if v >= -1 else -1) for k,v in var_output.items()}

        return {
            'ratio': current_ratio,
            'IL_type': impermenant_loss_type,
            'var': var_output}
