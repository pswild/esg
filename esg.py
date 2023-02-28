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

dispatch_stack_file = os.path.join(here, 'output/dispatch_stack.csv')

#--- FUNCTIONS ---#

def summarize_portfolios(supply):
    '''Summarize portfolios.'''

    # Define weighted average.
    weighted = lambda x: np.average(x, weights=supply.loc[x.index, 'mw'])
    
    # Group by portfolio. 
    portfolios = supply.groupby('portfolio_name', as_index=False).agg(agg_cap=('mw', 'sum'), agg_fixom=('fixom', 'sum'), wa_vom=('mc', weighted))
    
    # print(portfolios)

    return

def simulate(supply, demand):
    '''Baseline scenario for portfolio profitability using merit order dispatch.'''

    # Hourly financials by portfolio. 
    results = pd.DataFrame()

    for _, period in demand.iterrows():

        # Period. 
        day = period['day']
        hour = period['hour']
        load = period['load']

        # print('Day, ', day)
        # print('Hour ', hour)
        # print('Load ', load)

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
        
        # Calculate clearing price under zero profit condition. 
        cp = dispatch.loc[marginal]['mc']

        # Calculate revenue for each unit. 
        dispatch['revenue'] = dispatch['gen'] * (cp - dispatch['mc'])

        # Calculate revenue for each portfolio.
        portfolios = dispatch.groupby('portfolio_name', as_index=False).agg({'revenue': 'sum'})

        # Map hourly cost onto each portfolio.
        portfolios['cost'] = portfolios['portfolio_name'].map(hrly_costs)

        # Calculate profit for each portfolio. 
        portfolios['profit'] = portfolios['revenue'] + portfolios['cost']

        # Add period identifiers. 
        portfolios['day'] = day
        portfolios['hour'] = hour

        # Reformat.
        portfolios = portfolios[['day', 'hour', 'portfolio_name', 'revenue', 'cost', 'profit']]

        # Add to results.
        results = pd.concat([results, portfolios])

    return results

def cashflow(results, portfolio, overhead=225000, r=0.05):
    '''Calculate cashflow of given portfolio based on expected profitability and interest payments.'''

    # Group profits by day. 
    financials = results.groupby(['day', 'portfolio_name'], as_index=False).agg({'profit': 'sum'})

    # Slice by portfolio.
    financials = financials.loc[financials['portfolio_name'] == portfolio]

    # Add columns.
    financials['owed'] = None
    financials['payment'] = None
    financials['cash_flow'] = None

    # Financing balance. 
    owed = overhead

    for day in range(1,7):

        # Calculate interest at beginning of each day. 
        owed *= (1 + r)

        # Track what is owed at the beginning each day.
        financials.loc[financials['day'] == day, 'owed'] = owed

        # Cash inflow.
        inflow = financials.loc[financials['day'] == day, 'profit'].iloc[0]

        # Pay off debt.
        if inflow < 0:

            # Update payment.
            financials.loc[financials['day'] == day, 'payment'] = 0

            # Update cashflow for period. 
            financials.loc[financials['day'] == day, 'cash_flow'] = inflow

            # Update owed. 
            owed -= inflow

        elif inflow <= owed:

            # Update payment.
            financials.loc[financials['day'] == day, 'payment'] = inflow

            # Update cashflow for period. 
            financials.loc[financials['day'] == day, 'cash_flow'] = 0

            # Update owed. 
            owed -= inflow
        
        elif owed > 0: 

            # Update payment.
            financials.loc[financials['day'] == day, 'payment'] = owed

            # Update cashflow for period. 
            financials.loc[financials['day'] == day, 'cash_flow'] = inflow - owed

            # Update owed. 
            owed = 0

        else:

            # Update payment.
            financials.loc[financials['day'] == day, 'payment'] = 0     

            # Update cashflow for period. 
            financials.loc[financials['day'] == day, 'cash_flow'] = inflow     
            
    return financials

def bid(day, hour, portfolio, demand, supply):
    '''Determine optimal bid for given portfolio on day at hour.'''



    return

if __name__ == '__main__':
    
    #--- DATA ---

    supply = pd.read_csv(supply_file)
    demand = pd.read_csv(demand_file)

    #--- PORTFOLIOS ---#
    
    summarize_portfolios(supply)

    #--- BASELINE ---#

    # Calculate portfolio profits under merit order dispatch.
    results = simulate(supply, demand)

    # Group profits by portfolio. 
    profits = results.groupby(['portfolio_name'], as_index=False).agg({'profit': 'sum'})

    #--- FINANCIALS ---#

    # Overhead. 
    overhead = 225000

    # Calculate cashflow of desired portfolio given results.
    financials = cashflow(results, 'Fossil_Light', overhead, 0.05)

    # Calculate ROI. 
    roi = (financials['cash_flow'].sum()/overhead)*100

    # --- BIDDING ---#
    
