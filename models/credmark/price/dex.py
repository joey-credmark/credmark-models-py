# pylint: disable=locally-disabled, unused-import
from abc import abstractmethod
from typing import List

import pandas as pd
from credmark.cmf.model import Model, ModelDataErrorDesc
from credmark.cmf.model.errors import ModelDataError, ModelRunError
from credmark.cmf.types import Price, Token
from credmark.cmf.types.compose import MapInputsOutput
from models.dtos.price import PoolPriceAggregatorInput, PoolPriceInfos

PRICE_DATA_ERROR_DESC = ModelDataErrorDesc(
    code=ModelDataError.Codes.NO_DATA,
    code_desc='No pools to aggregate for token price')


@Model.describe(slug='price.pool-aggregator',
                version='1.3',
                display_name='Token Price from DEX pools, weighted by liquidity',
                description='Aggregate prices from pools weighted by liquidity',
                input=PoolPriceAggregatorInput,
                category='protocol',
                subcategory='compound',
                tags=['price'],
                output=Price,
                errors=PRICE_DATA_ERROR_DESC)
class PoolPriceAggregator(Model):
    def run(self, input: PoolPriceAggregatorInput) -> Price:
        if len(input.infos) == 0:
            raise ModelRunError(f'No pool to aggregate for {input.token}')

        df = pd.DataFrame(input.dict()['infos'])

        if len(input.infos) == 1:
            return Price(price=input.infos[0].price, src=input.price_src)

        product_of_price_liquidity = (df.price * df.liquidity ** input.weight_power).sum()
        sum_of_liquidity = (df.liquidity ** input.weight_power).sum()
        price = product_of_price_liquidity / sum_of_liquidity
        return Price(price=price, src=input.price_src)


class PriceWeight:
    WEIGHT_POWER = 1.0
    # TODO: more price weight-related methods


class DexWeightedPrice(Model, PriceWeight):
    @abstractmethod
    def run(self, input):
        ...

    def aggregate_pool(self, model_slug, input: Token):
        pool_price_infos = self.context.run_model(model_slug,
                                                  input=input)
        pool_aggregator_input = PoolPriceAggregatorInput(token=input,
                                                         **pool_price_infos,
                                                         price_src=self.slug,
                                                         weight_power=self.WEIGHT_POWER)
        return self.context.run_model('price.pool-aggregator',
                                      input=pool_aggregator_input,
                                      return_type=Price)


@Model.describe(slug='uniswap-v3.get-weighted-price',
                version='1.2',
                display_name='Uniswap v3 - get price weighted by liquidity',
                description='The Uniswap v3 pools that support a token contract',
                category='protocol',
                subcategory='uniswap-v3',
                tags=['price'],
                input=Token,
                output=Price,
                errors=PRICE_DATA_ERROR_DESC)
class UniswapV3WeightedPrice(DexWeightedPrice):
    def run(self, input: Token) -> Price:
        return self.aggregate_pool('uniswap-v3.get-pool-info-token-price', input)


@Model.describe(slug='uniswap-v2.get-weighted-price',
                version='1.2',
                display_name='Uniswap v2 - get price weighted by liquidity',
                description='The Uniswap v2 pools that support a token contract',
                category='protocol',
                subcategory='uniswap-v2',
                tags=['price'],
                input=Token,
                output=Price,
                errors=PRICE_DATA_ERROR_DESC)
class UniswapV2WeightedPrice(DexWeightedPrice):
    def run(self, input: Token) -> Price:
        return self.aggregate_pool('uniswap-v2.get-pool-info-token-price', input)


@Model.describe(slug='sushiswap.get-weighted-price',
                version='1.2',
                display_name='Sushi v2 (Uniswap V2) - get price weighted by liquidity',
                description='The Sushi v2 pools that support a token contract',
                category='protocol',
                subcategory='sushi-v2',
                tags=['price'],
                input=Token,
                output=Price,
                errors=PRICE_DATA_ERROR_DESC)
class SushiV2GetAveragePrice(DexWeightedPrice):
    def run(self, input: Token) -> Price:
        return self.aggregate_pool('sushiswap.get-pool-info-token-price', input)


@ Model.describe(slug='price.dex-blended',
                 version='1.7',
                 display_name='Token price - Credmark',
                 description='The Current Credmark Supported Price Algorithms',
                 developer='Credmark',
                 category='protocol',
                 subcategory='compound',
                 tags=['price'],
                 input=Token,
                 output=Price,
                 errors=PRICE_DATA_ERROR_DESC)
class PriceFromDexModel(Model, PriceWeight):
    """
    Return token's price
    """
    DEX_POOL_PRICE_INFO_MODELS: List[str] = ['uniswap-v2.get-pool-info-token-price',
                                             'sushiswap.get-pool-info-token-price',
                                             'uniswap-v3.get-pool-info-token-price']

    def run(self, input: Token) -> Price:
        model_inputs = [{"modelSlug": slug, "modelInputs": [input]}
                        for slug in self.DEX_POOL_PRICE_INFO_MODELS]

        def _use_compose():
            all_pool_infos_results = self.context.run_model(
                slug='compose.map-inputs',
                input={'modelSlug': 'compose.map-inputs',
                       'modelInputs': model_inputs},
                return_type=MapInputsOutput[dict, MapInputsOutput[dict, PoolPriceInfos]])

            all_pool_infos = []
            for dex_n, dex_result in enumerate(all_pool_infos_results):
                if dex_result.output is not None:
                    for pool_result in dex_result.output:
                        if pool_result.output is not None:
                            all_pool_infos.extend(pool_result.output)
                        elif pool_result.error is not None:
                            self.logger.error(pool_result.error)
                            raise ModelRunError(
                                f'Error with {model_inputs[dex_n]}'
                                f'({pool_result.input}). ' +
                                pool_result.error.message)
                elif dex_result.error is not None:
                    self.logger.error(dex_result.error)
                    raise ModelRunError(
                        f'Error with {model_inputs[dex_n]}. ' +
                        dex_result.error.message)
                else:
                    raise ModelRunError('compose.map-inputs: output/error cannot be both None')
            return all_pool_infos

        def _use_for():
            all_pool_infos = []
            for mrun in model_inputs:
                infos = self.context.run_model(mrun['modelSlug'],
                                               mrun['modelInputs'][0],
                                               PoolPriceInfos)
                all_pool_infos.extend(infos.infos)
            return all_pool_infos

        all_pool_infos = _use_for()

        non_zero_pools = {ii.src for ii in all_pool_infos if ii.liquidity > 0}
        zero_pools = {ii.src for ii in all_pool_infos if ii.liquidity == 0}
        pool_aggregator_input = PoolPriceAggregatorInput(
            token=input,
            infos=all_pool_infos,
            price_src=(f'{self.slug}|'
                       f'Non-zero:{",".join(non_zero_pools)}|'
                       f'Zero:{",".join(zero_pools)}'),
            weight_power=self.WEIGHT_POWER)
        return self.context.run_model('price.pool-aggregator',
                                      input=pool_aggregator_input,
                                      return_type=Price)
