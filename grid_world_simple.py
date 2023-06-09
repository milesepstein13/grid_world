import matplotlib
matplotlib.use('Agg')

import numpy as np
from matplotlib import pyplot as plt
from joblib import Parallel, delayed

from mushroom_rl.algorithms.value import QLearning, DoubleQLearning,\
    WeightedQLearning, SpeedyQLearning, SARSA,\
        SARSALambda, ExpectedSARSA, QLambda, RLearning, MaxminQLearning, RQLearning,\
            FQI, DoubleFQI, BoostedFQI, LSPI # These guys need an approximator?
from mushroom_rl.core import Core, Logger
from mushroom_rl.environments import *
from mushroom_rl.policy import EpsGreedy
from mushroom_rl.utils.callbacks import CollectDataset, CollectMaxQ
from mushroom_rl.utils.dataset import parse_dataset
from mushroom_rl.utils.parameters import ExponentialParameter
from sklearn.ensemble import ExtraTreesRegressor
import time


"""
This script aims to replicate the experiments on the Grid World MDP as
presented in:
"Double Q-Learning", Hasselt H. V.. 2010.
SARSA and many variants of Q-Learning are used. 
"""


def experiment(algorithm_class, exp):
    np.random.seed()

    TD_agents = [QLearning, DoubleQLearning, WeightedQLearning, SpeedyQLearning, SARSA, SARSALambda, ExpectedSARSA, QLambda, RLearning, MaxminQLearning, RQLearning]

    # MDP
    mdp = GridWorldVanHasselt()

    # Policy
    epsilon = ExponentialParameter(value=1, exp=.5, size=mdp.info.observation_space.size)
    pi = EpsGreedy(epsilon=epsilon)

    # Agent
    learning_rate = ExponentialParameter(value=1, exp=exp, size=mdp.info.size)
    algorithm_params = dict(learning_rate=learning_rate)
    
    # ADD EXTRA ALGORITHM PARAMS IF NEEDED 
    if algorithm_class in [SARSALambda, QLambda]:
        algorithm_params['lambda_coeff'] = .5 # https://ieeexplore.ieee.org/abstract/document/8798608, https://proceedings.mlr.press/v32/sutton14.html
    if algorithm_class in [RLearning, RQLearning]:
        algorithm_params['beta'] = .01 # http://incompleteideas.net/book/ebook/node67.html/https://web.stanford.edu/class/psych209/Readings/SuttonBartoIPRLBook2ndEd.pdf
    if algorithm_class in [MaxminQLearning]:
        algorithm_params['n_tables'] = 2 # We can tune n to balance over and under estimation! Would be something good to play with https://arxiv.org/pdf/2002.06487.pdf 


    if algorithm_class in [FQI]:
        # reference: https://github.com/MushroomRL/mushroom-rl/blob/dev/examples/car_on_hill_fqi.py
        approximator_params = dict(input_shape=mdp.info.observation_space.shape,
                               n_actions=mdp.info.action_space.n,
                               n_estimators=50,
                               min_samples_split=5,
                               min_samples_leaf=2)
        approximator = ExtraTreesRegressor
        algorithm_params = dict(approximator = approximator, n_iterations = 10, approximator_params = approximator_params)
        


    if algorithm_class in TD_agents:
        agent = algorithm_class(mdp.info, pi, **algorithm_params)
    elif algorithm_class in [FQI]:
        agent = algorithm_class(mdp.info, pi, **algorithm_params)

    # Algorithm
    if algorithm_class in TD_agents:
        start = mdp.convert_to_int(mdp._start, mdp._width)
        collect_max_Q = CollectMaxQ(agent.Q, start)
        collect_dataset = CollectDataset()
        callbacks = [collect_dataset, collect_max_Q]
        core = Core(agent, mdp, callbacks)
    elif algorithm_class in [FQI]:
        core = Core(agent, mdp)
        
    # Train
    if algorithm_class in TD_agents:
        core.learn(n_steps=10000, n_steps_per_fit=1, quiet=True) #fewer steps for debugging
    elif algorithm_class in [FQI]:
        core.learn(n_episodes=10, n_episodes_per_fit=10)
    ## may need to call learn with different parameters for some agents

    _, _, reward, _, _, _ = parse_dataset(collect_dataset.get())
    max_Qs = collect_max_Q.get()

    return reward, max_Qs


if __name__ == '__main__':
    n_experiment = 10000

    logger = Logger(QLearning.__name__, results_dir=None)
    logger.strong_line()
    logger.info('Experiment Algorithm: ' + QLearning.__name__)

    names = {1: '1', .8: '08', QLearning: 'Q', DoubleQLearning: 'DQ',
             WeightedQLearning: 'WQ', SpeedyQLearning: 'SPQ', SARSA: 'SARSA',
             SARSALambda: 'SARSAL', ExpectedSARSA: 'ESARSA', QLambda: 'QL', RLearning: 'RL', MaxminQLearning: 'MMQ', RQLearning: 'RQ', FQI: 'FQI'}

    file = open('nps_simple/times.txt', 'w')
    file.write('')
    file.close()

    for e in [.8]:
        logger.info(f'Exp: {e}')
        fig = plt.figure()
        plt.suptitle(names[e])
        legend_labels = []
        ticbig = time.perf_counter()
        for a in [QLearning, DoubleQLearning, WeightedQLearning,
                  SpeedyQLearning, SARSA, SARSALambda, ExpectedSARSA, QLambda, RLearning, MaxminQLearning, RQLearning,]: # could add FQI
            
            tic = time.perf_counter()

            logger.info(f'Alg: {names[a]}')
            out = Parallel(n_jobs=-1)(
                delayed(experiment)(a, e) for _ in range(n_experiment))
            r = np.array([o[0] for o in out])
            max_Qs = np.array([o[1] for o in out])

            r = np.convolve(np.mean(r, 0), np.ones(100) / 100., 'valid')
            max_Qs = np.mean(max_Qs, 0)

            toc = time.perf_counter()

            file = open('results_simple/times.txt', 'a')
            file.write('Method ' + names[a] + ' took ' + str((toc-tic)/60) + ' minutes.')
            file.write("\n")
            file.close()

            np.save('nps_simple/' + names[a] + '_' + names[e] + '_r.npy', r)
            np.save('nps_simple/' + names[a] + '_' + names[e] + '_maxQ.npy', max_Qs)

            print("r")
            print(r)

            print("Max Qs")
            print(max_Qs)

            plt.subplot(1, 1)
            plt.plot(r)
            plt.title("r")
            plt.subplot(1, 2)
            plt.plot(max_Qs)
            plt.title("Max Qs")
            legend_labels.append(names[a])
        plt.legend(legend_labels)
        fig.savefig('results_simple/test_' + names[e] + '.png')


        tocbig = time.perf_counter()
        file = open('results_simple/times.txt', 'a')
        file.write('Overall: ' + str((tocbig-ticbig)/60) + ' minutes.')
        file.close()