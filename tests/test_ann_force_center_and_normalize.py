from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import numpy as np
import tensorflow as tf
from openkim_fit.dataset import DataSet
from openkim_fit.descriptor import Descriptor
import openkim_fit.ann as ann

# Check that the forces and energys are the same with the KIM model.
# 1. run this script
# 2. copy `ann_kim.params' generated by this script to the KIM MoS2 model, and make.
# 3. run LAMMPS with input `lammps_mos2.in' to generate the dump file.
# 4. compare the stdout of this script and the LAMMPS dump file.
#
# Note that sess.run(...) will cause iterator.get_next() to fetch next batch. So
# if multiple sess.run(...) is called, they wil not evaluate the same configuration.
# So make sure the use one sess.run(...). Comment one when you want to evaluate
# another quantity.


# set a global random seed
DTYPE = tf.float64
tf.set_random_seed(1)


# create Descriptor
cutfunc = 'cos'
cutvalue = {'Mo-Mo':5., 'Mo-S':5., 'S-S':5.}
desc_params = {'g1': None,
                 'g2': [{'eta':0.1, 'Rs':0.2},
                        {'eta':0.3, 'Rs':0.4}],
                 'g3': [{'kappa':0.1},
                        {'kappa':0.2},
                        {'kappa':0.3}],
                 'g4': [{'zeta':0.1, 'lambda':0.2, 'eta':0.01},
                        {'zeta':0.3, 'lambda':0.4, 'eta':0.02}],
                 'g5': [{'zeta':0.11, 'lambda':0.22, 'eta':0.011},
                        {'zeta':0.33, 'lambda':0.44, 'eta':0.022}]
                }

desc = Descriptor(cutfunc, cutvalue, desc_params)


# read config and reference data
tset = DataSet()
tset.read('./training_set/training_set_mos2_small_config_4/')
configs = tset.get_configs()


# preprocess data to generate tfrecords
train_name, validation_name = ann.convert_raw_to_tfrecords(configs, desc,
    directory='/tmp/dataset_tfrecords', do_generate=True, dtype=tf.float64)
# read data from tfrecords into tensors
dataset = ann.read_from_tfrecords(train_name, dtype=tf.float64)
dataset = dataset.repeat(10)
dataset = dataset.batch(1)
iterator = dataset.make_one_shot_iterator()
next_batch = iterator.get_next()    # batch size of

# create shared params (we need to share params among different config, so create first)
num_desc = desc.get_num_descriptors()
weights, biases = ann.parameters(num_desc, [20, 20, 1], dtype=DTYPE)


#######################################
# create graph
#######################################
# unpack data from tfRecords
atomic_coords = next_batch[0]
gen_coords = next_batch[1]
dgen_datomic_coords = next_batch[2]
energy_label = next_batch[3]
forces_label = next_batch[4]

# configure in batch
conf_idx = 0
r = atomic_coords[conf_idx]
zeta = gen_coords[conf_idx]
dzetadr = dgen_datomic_coords[conf_idx]

in_layer = ann.input_layer_given_data(r, zeta, dzetadr)
dense1 = ann.nn_layer(in_layer, weights[0], biases[0], 'hidden1',act=tf.nn.tanh)
dense2 = ann.nn_layer(dense1, weights[1], biases[1], 'hidden2', act=tf.nn.tanh)
output = ann.output_layer(dense2, weights[2], biases[2], 'outlayer')

# energy and forces
energy = tf.reduce_sum(output)
forces = tf.gradients(output, r)[0]  # tf.gradients return a LIST of tensors


with tf.Session() as sess:

  # init global vars
  init_op = tf.global_variables_initializer()
  sess.run(init_op)

  print('\n\n', '='*80)

#  out = sess.run(atomic_coords[conf_idx])
#  print('coords:')
#  print(out)
#  print('coords (nicer output):')
#  for i,f in enumerate(out):
#    print('{:13.5e}'.format(f), end='')
#    if i%3==2:
#      print()


#  out = sess.run(gen_coords[conf_idx])
#  print('generalized coords:')
#  print(out)


#  out = sess.run(energy)
#  print('energy:\n', out)


  out = sess.run(forces)
  print('forces:')
  print (out)
  print('forces (nicer output):')
  for i,f in enumerate(out):
    print('{:13.5e}'.format(f), end='')
    if i%3==2:
      print()



  # output results to a KIM model
  w,b = sess.run([weights, biases])
  ann.write_kim_ann(desc, w, b, tf.nn.tanh, tf.float64)