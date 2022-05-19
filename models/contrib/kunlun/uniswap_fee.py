from datetime import date, datetime, timezone
from credmark.cmf.model import Model
from credmark.dto import DTO

from credmark.cmf.types import BlockNumber, Token, Contract, Address
from credmark.cmf.types.ledger import TokenTransferTable
import pandas as pd


def get_dt(year: int, month: int, day: int, hour=0, minute=0, second=0, microsecond=0):
    """Get a datetime for date and time values"""
    return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)


def get_block(in_dt: datetime):
    """Get the BlockNumber instance at or before the datetime timestamp."""
    return BlockNumber.from_timestamp(in_dt.replace(tzinfo=timezone.utc).timestamp())


class UniswapFeeInput(DTO):
    start_date: date
    end_date: date
    pool_addr: Address = Address('0xcbcdf9626bc03e24f779434178a73a0b4bad62ed')


@Model.describe(slug='contrib.uniswap-fee',
                version='1.0',
                display_name='Calculate fee from swaps in Uniswap V3 pool',
                description="Ledger",
                input=UniswapFeeInput,
                output=dict)
class UniswapFee(Model):

    def run(self, input: UniswapFeeInput) -> dict:
        uni_pool_addr = input.pool_addr
        univ3_btcweth_pool = Contract(address=uni_pool_addr)
        t0 = Token(address=univ3_btcweth_pool.functions.token0().call())
        t1 = Token(address=univ3_btcweth_pool.functions.token1().call())
        t0_addr = t0.address
        t1_addr = t1.address
        fee = univ3_btcweth_pool.functions.fee().call()

        # get block numbers on the dates
        block_start = get_block(get_dt(input.start_date.year, input.start_date.month, input.start_date.day))
        block_end = get_block(get_dt(input.end_date.year, input.end_date.month, input.end_date.day))

        # Query the ledger for the token transfers
        ledger = self.context.ledger
        df_tx_out = ledger.get_erc20_transfers(
            columns=[TokenTransferTable.Columns.BLOCK_NUMBER,
                     TokenTransferTable.Columns.TOKEN_ADDRESS,
                     TokenTransferTable.Columns.TRANSACTION_HASH,
                     TokenTransferTable.Columns.FROM_ADDRESS,
                     TokenTransferTable.Columns.TO_ADDRESS,
                     TokenTransferTable.Columns.VALUE,
                     ],
            where=(f'{TokenTransferTable.Columns.BLOCK_NUMBER} > {block_start} AND {TokenTransferTable.Columns.BLOCK_NUMBER} <= {block_end} AND '
                   f'{TokenTransferTable.Columns.FROM_ADDRESS} = \'{uni_pool_addr}\'')).to_dataframe()

        df_tx_in = ledger.get_erc20_transfers(
            columns=[TokenTransferTable.Columns.BLOCK_NUMBER,
                     TokenTransferTable.Columns.TOKEN_ADDRESS,
                     TokenTransferTable.Columns.TRANSACTION_HASH,
                     TokenTransferTable.Columns.FROM_ADDRESS,
                     TokenTransferTable.Columns.TO_ADDRESS,
                     TokenTransferTable.Columns.VALUE
                     ],
            where=(f'{TokenTransferTable.Columns.BLOCK_NUMBER} > {block_start} AND {TokenTransferTable.Columns.BLOCK_NUMBER} <= {block_end} AND '
                   f'{TokenTransferTable.Columns.TO_ADDRESS} = \'{uni_pool_addr}\'')).to_dataframe()

        assert df_tx_in.loc[df_tx_in.value == '', :].shape[0] == 0
        assert df_tx_out.loc[df_tx_out.value == '', :].shape[0] == 0

        df_tx_in.value = df_tx_in.value.astype(float)
        df_tx_out.value = df_tx_out.value.astype(float) * (-1)

        df_tx_total = pd.concat([df_tx_out, df_tx_in]).query('token_address in [@t0_addr, @t1_addr]')

        # Only keep those swap transactions
        df_groupby_hash = df_tx_total.groupby('transaction_hash', as_index=False).token_address.count()
        _df_tx_non_swap = df_tx_total.merge(df_groupby_hash.loc[(
            df_groupby_hash.token_address != 2), :], on='transaction_hash', how='inner')

        # Use the swap transactions hashes to filter all transactions
        df_tx_swap = df_tx_total.merge(df_groupby_hash.loc[(
            df_groupby_hash.token_address == 2), ['transaction_hash']], how='inner')

        # Summarize the swap transaction from two rows to one row
        full_tx = []
        for dfg, df in df_tx_swap.groupby('transaction_hash', as_index=False):
            assert df.shape[0] == 2
            if df.value.product() < 0:
                t0_amount = t0.scaled(df.loc[df.token_address == t0_addr, 'value'].to_list()[0])
                t1_amount = t1.scaled(df.loc[df.token_address == t1_addr, 'value'].to_list()[0])
                if df.to_address.to_list()[0] == uni_pool_addr:
                    full_tx.append((dfg, df.block_number.to_list()[0],
                                    df.from_address.to_list()[0], df.to_address.to_list()[1],
                                    t0_amount, t1_amount, t1_amount / t0_amount))
                elif df.to_address.to_list()[1] == uni_pool_addr:
                    full_tx.append((dfg, df.block_number.to_list()[0],
                                    df.from_address.to_list()[1], df.to_address.to_list()[0],
                                    t0_amount, t1_amount, t1_amount / t0_amount))
                else:
                    raise ValueError('Cannot match tradeas\' from and to')

        df_tx_swap_one_line = pd.DataFrame(
            full_tx, columns=['transaction_hash', 'block_number', 'from', 'to', 't0_amount', 't1_amount', 't1/t0'])

        # Fee model: take the incoming amount's X.X% from pool's fee value.
        # TODO: my rough idea of how the fee is collected. I might be wrong.

        def calculate_fee(r, self, t0, t1, fee):
            t0_price = self.context.models(r['block_number']).chainlink.price_usd(t0)['price']
            t1_price = self.context.models(r['block_number']).chainlink.price_usd(t1)['price']
            if r['t0_amount'] > 0:
                in_value = t0_price * r['t0_amount']
                out_value = t1_price * r['t1_amount']
            else:
                in_value = t1_price * r['t1_amount']
                out_value = t0_price * r['t0_amount']
            return in_value, out_value, in_value / (1 + fee / 1_000_000) * fee / 1_000_000

        df_new_cols = df_tx_swap_one_line.apply(
            lambda r, self=self, t0=t0, t1=t1, fee=fee:
            calculate_fee(r, self, t0, t1, fee), axis=1, result_type='expand')

        df_new_cols.columns = pd.Index(['in_value', 'out_value', 'fee'])

        df_tx_swap_one_line = pd.concat([df_tx_swap_one_line, df_new_cols], axis=1)

        df_tx_swap_one_line.in_value.sum()

        return {'block_start': block_start,
                'block_end': block_end,
                'block_start_time': BlockNumber(block_start).timestamp_datetime,
                'block_end_time': BlockNumber(block_end).timestamp_datetime,
                'pool_address': uni_pool_addr,
                'tx_number': df_tx_swap_one_line.shape[0],
                'fee_rate': fee,
                'total_fee': df_tx_swap_one_line.fee.sum(),
                'total_tx_in_value': df_tx_swap_one_line.in_value.sum(),
                'total_tx_out_value': df_tx_swap_one_line.out_value.sum()}
