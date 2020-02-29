#!/usr/bin/env python
# encoding: utf-8
"""
@author: HuRuiFeng
@file: 11.12-sentiment-analysis-layer-LSTM-pretrain.py
@time: 2020/2/28 16:25
@desc: 11.12 预训练的词向量的代码（LSTM layer方式）
       将glove.6B文件夹放到ch11目录下，读取的glove路径为/ch11/glove.6B/glove.6B.100d.txt
"""

import os

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, losses, optimizers, Sequential

tf.random.set_seed(22)
np.random.seed(22)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'


def load_dataset(batchsz, total_words, max_review_len, embedding_len):
    # 加载IMDB数据集，此处的数据采用数字编码，一个数字代表一个单词
    (x_train, y_train), (x_test, y_test) = keras.datasets.imdb.load_data(num_words=total_words)
    print(x_train.shape, len(x_train[0]), y_train.shape)
    print(x_test.shape, len(x_test[0]), y_test.shape)

    # x_train:[b, 80]
    # x_test: [b, 80]
    # 截断和填充句子，使得等长，此处长句子保留句子后面的部分，短句子在前面填充
    x_train = keras.preprocessing.sequence.pad_sequences(x_train, maxlen=max_review_len)
    x_test = keras.preprocessing.sequence.pad_sequences(x_test, maxlen=max_review_len)
    # 构建数据集，打散，批量，并丢掉最后一个不够batchsz的batch
    db_train = tf.data.Dataset.from_tensor_slices((x_train, y_train))
    db_train = db_train.shuffle(1000).batch(batchsz, drop_remainder=True)
    db_test = tf.data.Dataset.from_tensor_slices((x_test, y_test))
    db_test = db_test.batch(batchsz, drop_remainder=True)
    print('x_train shape:', x_train.shape, tf.reduce_max(y_train), tf.reduce_min(y_train))
    print('x_test shape:', x_test.shape)
    return db_train, db_test


def pretrain_embeding_matrix(embedding_len, total_words):
    # 数字编码表
    word_index = keras.datasets.imdb.get_word_index()

    word_index = {k: (v + 3) for k, v in word_index.items()}
    word_index["<PAD>"] = 0
    word_index["<START>"] = 1
    word_index["<UNK>"] = 2  # unknown
    word_index["<UNUSED>"] = 3

    print('Indexing word vectors.')
    embeddings_index = {}
    GLOVE_DIR = r'.\glove.6B'
    with open(os.path.join(GLOVE_DIR, 'glove.6B.100d.txt'), encoding='utf-8') as f:
        for line in f:
            values = line.split()
            word = values[0]
            coefs = np.asarray(values[1:], dtype='float32')
            embeddings_index[word] = coefs
    print('Found %s word vectors.' % len(embeddings_index))
    MAX_NUM_WORDS = total_words
    # prepare embedding matrix
    num_words = min(MAX_NUM_WORDS, len(word_index))
    embedding_matrix = np.zeros((num_words, embedding_len))
    applied_vec_count = 0
    for word, i in word_index.items():
        if i >= MAX_NUM_WORDS:
            continue
        embedding_vector = embeddings_index.get(word)
        # print(word,embedding_vector)
        if embedding_vector is not None:
            # words not found in embedding index will be all-zeros.
            embedding_matrix[i] = embedding_vector
            applied_vec_count += 1

    return embedding_matrix


class MyRNN(keras.Model):
    # Cell方式构建多层网络
    def __init__(self, units, total_words, embedding_len, max_review_len, embedding_matrix):
        super(MyRNN, self).__init__()
        # 词向量编码 [b, 80] => [b, 80, 100]
        # 创建 Embedding 层
        self.embedding = layers.Embedding(total_words, embedding_len,
                                          input_length=max_review_len,
                                          trainable=False)
        self.embedding.build(input_shape=(None, max_review_len))
        # 利用 GloVe 模型初始化 Embedding 层
        self.embedding.set_weights([embedding_matrix])  # 初始化
        # 构建RNN
        self.rnn = Sequential([
            layers.LSTM(units, dropout=0.5, return_sequences=True),
            layers.LSTM(units, dropout=0.5)
        ])

        # 构建分类网络，用于将CELL的输出特征进行分类，2分类
        # [b, 80, 100] => [b, 64] => [b, 1]
        self.outlayer = Sequential([
            layers.Dense(32),
            layers.Dropout(rate=0.5),
            layers.ReLU(),
            layers.Dense(1)])

    def call(self, inputs, training=None):
        x = inputs  # [b, 80]
        # embedding: [b, 80] => [b, 80, 100]
        x = self.embedding(x)
        # rnn cell compute,[b, 80, 100] => [b, 64]
        x = self.rnn(x)
        # 末层最后一个输出作为分类网络的输入: [b, 64] => [b, 1]
        x = self.outlayer(x, training)
        # p(y is pos|x)
        prob = tf.sigmoid(x)

        return prob


def main():
    batchsz = 128  # 批量大小
    total_words = 10000  # 词汇表大小N_vocab
    embedding_len = 100  # 词向量特征长度f
    max_review_len = 80  # 句子最大长度s，大于的句子部分将截断，小于的将填充

    db_train, db_test = load_dataset(batchsz, total_words, max_review_len, embedding_len)

    units = 32  # RNN状态向量长度f
    epochs = 20  # 训练epochs
    embedding_matrix = pretrain_embeding_matrix(embedding_len, total_words)

    model = MyRNN(units, total_words, embedding_len, max_review_len, embedding_matrix)
    # 装配
    model.compile(optimizer=optimizers.RMSprop(0.001),
                  loss=losses.BinaryCrossentropy(),
                  metrics=['accuracy'],
                  experimental_run_tf_function=False)
    # 训练和验证
    model.fit(db_train, epochs=epochs, validation_data=db_test)
    # 测试
    model.evaluate(db_test)


if __name__ == '__main__':
    main()