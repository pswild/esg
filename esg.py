# -*- coding: utf-8 -*-
#!/usr/bin/env python3

"""
Simulate baseline operation of ESG.

Created on Mon Feb 27 14:21:51 2022

@author: pswild
"""

import os
import numpy as np
import pandas as pd

#--- PATH ---# 

here = os.path.dirname(os.path.realpath(__file__))

#--- DATA ---#

supply_file = os.path.join(here, 'data/supply.csv')
demand_file = os.path.join(here, 'data/demand.csv')

# Portfolio names.
portfolio_names = [
    'Bay_Views',
    'Beachfront',
    'Big_Coal',
    'Big_Gas',
    'East_Bay',
    'Fossil_Light',
    'Old_Timers'
]

# Overhead cost by portfolio. 
overhead_costs = {
    'Bay_Views': 90000,
    'Beachfront': 185000,
    'Big_Coal': 165000,
    'Big_Gas': 100000,
    'East_Bay': 61500,
    'Fossil_Light': 225000,
    'Old_Timers': 185000
}

# Hourly cost by portfolio.
hrly_costs = {
    'Bay_Views': -5500,
    'Beachfront': -6750,
    'Big_Coal': -5000,
    'Big_Gas': -2000,
    'East_Bay': -4000,
    'Fossil_Light': -9250,
    'Old_Timers': -11250
}

#--- OUTPUT ---#

financials_file = os.path.join(here, 'outputs/financials.csv')
profitability_curve_file = os.path.join(here, 'outputs/profitability_curve.csv')
mb_curve_file = os.path.join(here, 'outputs/mb_curve.csv')

#--- FUNCTIONS ---#

def summarize_portfolios(supply):
    '''Summarize portfolios.'''

    # Define weighted average.
    weighted = lambda x: np.average(x, weights=supply.loc[x.index, 'mw'])
    
    # Group by portfolio. 
    portfolios = supply.groupby('portfolio_name', as_index=False).agg(agg_cap=('mw', 'sum'), agg_fixom=('fixom', 'sum'), wa_vom=('mc', weighted))
    
    # print(portfolios)

    return

def simulate(supply, load, offset=0):
    '''Calculate portfolio profitability for given load using merit order dispatch.'''

    # Dispatch instance. 
    dispatch = supply.copy()

    # Flag for inframarginal.
    dispatch['inframarginal'] = False

    # Flag for marginal. 
    dispatch['marginal'] = False

    # Set generation to zero.
    dispatch['gen'] = 0

    # Set revenue to zero. 
    dispatch['revenue'] = 0

    # Index of marginal unit.
    marginal = len(dispatch.loc[dispatch['cumulative'] < load])

    # Identify inframarginal units.
    dispatch.loc[:marginal - 1, 'inframarginal'] = True

    # Identify marginal unit.
    dispatch.loc[marginal, 'marginal'] = True

    # Update generation. 
    dispatch.loc[dispatch['inframarginal'], 'gen'] = dispatch['mw']
    dispatch.loc[dispatch['marginal'], 'gen'] = dispatch['mw'] - (dispatch['cumulative'] - load)
    
    # Calculate clearing price under zero profit condition (plus offset, if applicable). 
    cp = dispatch.loc[marginal]['mc'] + offset

    # Calculate revenue for each unit. 
    dispatch['revenue'] = dispatch['gen'] * (cp - dispatch['mc'])

    # Calculate revenue for each portfolio.
    portfolios = dispatch.groupby('portfolio_name', as_index=False).agg({'revenue': 'sum'})

    # Map hourly cost onto each portfolio.
    portfolios['cost'] = portfolios['portfolio_name'].map(hrly_costs)

    # Calculate profit for each portfolio. 
    portfolios['profit'] = portfolios['revenue'] + portfolios['cost']

    return portfolios

def profitability(supply):
    '''Estimate profitability for all portfolios at each level of demand.'''

    # Marginal benefit dataframe. 
    p = pd.DataFrame(columns=[portfolio_names])

    for d in range(1, supply['cumulative'].tail(1).iloc[0] + 1):

        # Simulate portfolio profitability with baseline clearing price. 
        profits = simulate(supply, d, 0)

        for _, portfolio in profits.iterrows():

            # Add to marginal benefit dataframe.
            p.at[d, portfolio['portfolio_name']] = portfolio['profit']

    return p

def mb_curve(supply):
    '''Estimate marginal benefit of market power for all portfolios at each level of demand.'''

    # Marginal benefit dataframe. 
    mb = pd.DataFrame(columns=[portfolio_names])

    for d in range(1, supply['cumulative'].tail(1).iloc[0] + 1):

        # Simulate portfolio profitability with baseline clearing price. 
        profits_t1 = simulate(supply, d, 0)

        # Rename column.
        profits_t1 = profits_t1.rename(columns={'profit': 'profit_t1'})
        profits_t1 = profits_t1[['portfolio_name', 'profit_t1']]

        # Simulate portfolio profitability with additional dollar added to clearing price.
        profits_t2 = simulate(supply, d, 1)

        # Rename column.
        profits_t2 = profits_t2.rename(columns={'profit': 'profit_t2'})
        profits_t2 = profits_t2[['portfolio_name', 'profit_t2']]

        # Merge. 
        profits = profits_t1.merge(profits_t2, on='portfolio_name')

        # Calculate marginal profit of each portfolio for given level of demand. 
        profits['marginal_benefit'] = profits['profit_t2'] - profits['profit_t1']

        for _, portfolio in profits.iterrows():

            # Add to marginal benefit dataframe.
            mb.at[d, portfolio['portfolio_name']] = portfolio['marginal_benefit']

    return mb

def bid(day, hour, portfolio, demand, supply):
    '''Determine optimal bid for given portfolio on day at hour under Cournot competition.'''

    print('Not yet implemented.')

    return

def roi(results, portfolio, overhead=225000, r=0.05):
    '''Calculate cashflow of given portfolio based on expected profitability and interest payments.'''

    # Group profits by day. 
    f = results.groupby(['day', 'portfolio_name'], as_index=False).agg({'profit': 'sum'})

    # Slice by portfolio.
    f = f.loc[f['portfolio_name'] == portfolio]

    # Add columns.
    f['owed'] = None
    f['payment'] = None
    f['cash_flow'] = None

    # Financing balance. 
    owed = overhead

    for day in range(1,7):

        # Calculate interest at beginning of each day. 
        owed *= (1 + r)

        # Track what is owed at the beginning each day.
        f.loc[f['day'] == day, 'owed'] = owed

        # Cash inflow.
        inflow = f.loc[f['day'] == day, 'profit'].iloc[0]

        # Pay off debt.
        if inflow < 0:

            # Update payment.
            f.loc[f['day'] == day, 'payment'] = 0

            # Update cashflow for period. 
            f.loc[f['day'] == day, 'cash_flow'] = inflow

            # Update owed. 
            owed -= inflow

        elif inflow <= owed:

            # Update payment.
            f.loc[f['day'] == day, 'payment'] = inflow

            # Update cashflow for period. 
            f.loc[f['day'] == day, 'cash_flow'] = 0

            # Update owed. 
            owed -= inflow
        
        elif owed > 0: 

            # Update payment.
            f.loc[f['day'] == day, 'payment'] = owed

            # Update cashflow for period. 
            f.loc[f['day'] == day, 'cash_flow'] = inflow - owed

            # Update owed. 
            owed = 0

        else:

            # Update payment.
            f.loc[f['day'] == day, 'payment'] = 0     

            # Update cashflow for period. 
            f.loc[f['day'] == day, 'cash_flow'] = inflow     
            
    return f

if __name__ == '__main__':
    
    #--- DATA ---

    supply = pd.read_csv(supply_file)
    demand = pd.read_csv(demand_file)

    #--- PORTFOLIOS ---#
    
    summarize_portfolios(supply)

    #--- BASELINE ---#

    # Hourly financials by portfolio. 
    financials = pd.DataFrame()

    for _, period in demand.iterrows():

        # Period. 
        day = period['day']
        hour = period['hour']
        load = period['load']

        # Calculate portfolio profits under merit order dispatch.
        output = simulate(supply, load, offset=0)

        # Add period identifiers. 
        output['day'] = day
        output['hour'] = hour

        # Add to dataframe.
        financials = pd.concat([financials, output])

    # Group financials by portfolio. 
    financials = financials.groupby(['day', 'portfolio_name'], as_index=False).agg({'cost': 'sum', 'revenue': 'sum', 'profit': 'sum'})

    # Write financials to CSV.
    financials.to_csv(financials_file, index=False)

    # Format financials.
    print(financials.groupby(['portfolio_name']).agg({'cost': 'sum', 'revenue': 'sum', 'profit': 'sum'}).sort_values(by='profit', ascending=False))

    #--- RETURN ON INVESTMENT ---#

    # ROIs dataframe.
    rois = pd.DataFrame(columns=['roi']) 

    for portfolio, overhead in overhead_costs.items():

        # Calculate cashflow of desired portfolio given results.
        output = roi(financials, portfolio, overhead, 0.05)

        # Add to dataframe. 
        rois.at[portfolio, 'roi'] = output['cash_flow'].sum()/overhead*100

    # Format ROIs. 
    rois = rois.sort_values(by='roi', ascending=False)

    print(rois)

    #--- PROFITABILITY ---#

    # For each level of demand, which portfolio is most profitable (assuming merit order dispatch)?
    # p = profitability(supply)

    # Write profitability curve to CSV.
    # p.to_csv(profitability_curve_file, index=False)

    #--- MARGINAL BENEFITS OF EXERCISING MARKET POWER ---#

    # For each level of demand, which portfolio benefits most from a higher market clearing price (assuming merit order dispatch)? 
    # mb = mb_curve(supply)

    # Write marginal benefit curve to CSV.
    # mb.to_csv(mb_curve_file, index=False)

    # --- BIDDING ---#

    # Requires game theoretic approach for full implementation.
