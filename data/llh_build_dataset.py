#!/usr/bin/python
# -*- coding:utf-8 -*-
import json
from tqdm import tqdm
from collections import Counter
import numpy as np
import json
from torch.utils.data import DataLoader
import argparse
from torch.utils import data
import pickle

class RCData(data.Dataset):

    def __init__(self, article, question, answer_span, word_match):
        self.len = article.shape[0]
        self.article = article  # (total_size, length_p)
        self.question = question  # (total_size, length_q)
        self.answer_span = answer_span  # (total_size, (start_idx, end_idx))
        self.word_match = word_match  # (total_size, length_p)

    def __getitem__(self, index):
        return self.article[index], self.question[index], self.answer_span[index], self.word_match[index]

    def __len__(self):
        return self.len

class RCValidData(data.Dataset):

    def __init__(self, article, question, word_match):
        self.len = article.shape[0]
        self.article = article  # (total_size, length_p)
        self.question = question  # (total_size, length_q)
        self.word_match = word_match  # (total_size, length_p)

    def __getitem__(self, index):
        return self.article[index], self.question[index], self.word_match[index]

    def __len__(self):
        return self.len

class RCTestData(data.Dataset):

    def __init__(self, article, question, word_match):
        self.len = article.shape[0]
        self.article = article  # (total_size, length_p)
        self.question = question  # (total_size, length_q)
        self.word_match = word_match  # (total_size, length_p)

    def __getitem__(self, index):
        return self.article[index], self.question[index], self.word_match[index]

    def __len__(self):
        return self.len


class Data():

    def __init__(self, args):
        self.data = self.load_data(args.train_file)
        self.max_article_len = args.max_article_len
        self.max_question_len = args.max_question_len
        self.max_answer_len = args.max_answer_len
        self.args = args
        self.min_count = args.min_count
        self.batch_size = args.batch_size
        self.word2idx_path = args.word2idx_path
        self.idx2word_path = args.idx2word_path
        self.word2idx, self.idx2word = None, None
        self.model_id = args.model_id

    def load_data(self, path):
        print("load ", path)
        data = json.load(open(path, "r", encoding="utf-8"))
        return data

    # def build_vocab(self):
    #     count = [("<UNK>", -1), ("<PAD>", -1)]
    #     words = []
    #
    #     for d in self.data:
    #         words.extend(list(d['article_title']))
    #         words.extend(list(d['article_content']))
    #         for qa in d['questions']:
    #             # 问题答案对
    #             if len(qa['question']) != 0 and len(qa['answer']) != 0:
    #                 words.extend(list(qa['question']))
    #                 words.extend(list(qa['answer']))
    #
    #     counter = Counter(words)
    #     counter_list = counter.most_common()
    #     print(len(counter_list))
    #     for word, c in counter_list:
    #         if c >= self.min_count:
    #             count.append((word, c))
    #     print("min_count:", self.min_count, "filter:", len(counter_list) - len(count))
    #     word2idx = dict()
    #     for word, _ in count:
    #         word2idx[word] = len(word2idx)
    #     idx2word = dict(zip(word2idx.values(), word2idx.keys()))
    #     json.dump(word2idx, open(self.word2idx_path, 'w', encoding="utf-8"), ensure_ascii=False)
    #     json.dump(idx2word, open(self.idx2word_path, 'w', encoding="utf-8"), ensure_ascii=False)
    #     self.word_vocab_size = len(word2idx)
    #     self.args.word_vocab_size = self.word_vocab_size
    #     print('word vocab size: ', self.word_vocab_size)
    #     self.word2idx = word2idx
    #     self.idx2word = idx2word

    def load_vocab(self):
        print("load vocab ... load vocab ... load vocab ...")
        self.word2idx = json.load(open(self.word2idx_path, "r", encoding="utf-8"))
        self.idx2word = json.load(open(self.idx2word_path, "r", encoding="utf-8"))
        self.word_vocab_size = len(self.word2idx)
        self.args.word_vocab_size = self.word_vocab_size
        print('word vocab size: ', self.word_vocab_size)

    def word2idx_for_list(self, temp_list):
        return [self.word2idx[w] if w in self.word2idx else 0 for w in temp_list]

    def build_dataset(self):
        article_list, question_list, answer_list, golden_span_list = [], [], [], []
        word_match = []
        raw_article_list = []
        raw_question_list = []

        for article_id, d in enumerate(self.data):

            temp_article = list(d['article_content'])
            if len(temp_article) == 0:
                continue
            if len(temp_article) > self.max_article_len:
                temp_article = temp_article[:self.max_article_len]
            else:
                temp_article.extend(["<PAD>"] * max(0, self.max_article_len - len(temp_article)))

            temp_article = self.word2idx_for_list(temp_article)

            for qa in d['questions']:
                # 问题答案对
                if len(qa['question']) != 0 and len(qa['answer']) != 0 \
                        and qa['answer_span'][0] != -1 and qa['answer_span'][1] != -1\
                        and qa['answer_span'][1] < self.max_article_len:    # TODO
                    article_list.append(temp_article)
                    temp_question = list(qa['question'])
                    if len(temp_question) > self.max_question_len:
                        temp_question = temp_question[:self.max_question_len]
                    else:
                        temp_question.extend(["<PAD>"] * max(0, self.max_question_len - len(temp_question)))
                    temp_question = self.word2idx_for_list(temp_question)
                    question_list.append(temp_question)

                    # 保留原始长度的answer
                    temp_answer = "".join(qa['answer'])
                    answer_list.append(temp_answer)
                    raw_article_list.append(list(d['article_content'])[:self.max_article_len]) # TODO
                    raw_question_list.append(list(qa['question']))
                    golden_span_list.append(qa['answer_span'])

                    tmp_word_match = [1 if w in list(qa['question']) else 0 for w in list(d['article_content'])]
                    if len(tmp_word_match) > self.max_article_len:
                        tmp_word_match = tmp_word_match[:self.max_article_len]
                    else:
                        tmp_word_match.extend([0] * max(0, self.max_article_len - len(tmp_word_match)))
                    word_match.append(tmp_word_match)


        article_list = np.array(article_list, dtype=np.int64)
        question_list = np.array(question_list, dtype=np.int64)
        golden_span_list = np.array(golden_span_list, dtype=np.int64)
        word_match = np.array(word_match, dtype=np.int64)

        # shuffle
        # shuffle_idx = np.arange(len(question_list))
        # np.random.shuffle(shuffle_idx)
        # pickle.dump(shuffle_idx, open("./shuffle_idx.json", "wb"))

        print("load shuffle_idx ...")
        shuffle_idx = pickle.load(open("./data/shuffle_idx.pkl", "rb"))
        article_list = article_list[shuffle_idx]
        question_list = question_list[shuffle_idx]
        golden_span_list = golden_span_list[shuffle_idx]
        answer_list = [answer_list[idx] for idx in shuffle_idx]
        raw_article_list = [raw_article_list[idx] for idx in shuffle_idx]
        raw_question_list = [raw_question_list[idx] for idx in shuffle_idx]

        train_size = len(question_list)
        print("total size:", train_size)
        valid_size = train_size // 10
        b = train_size
        e = train_size
        if self.args.with_valid:
            #train_size = int(train_size * 0.9)
            b = self.model_id*valid_size
            e = b + valid_size

        self.train_raw_article_list = raw_article_list[0:b] + raw_article_list[e:]
        self.train_raw_question_list = raw_question_list[0:b] + raw_question_list[e:]

        self.valid_raw_article_list = raw_article_list[b:e]
        self.valid_answer_list = answer_list[b:e]
        self.valid_raw_question_list = raw_question_list[b:e]

        # 训练、验证的总数据集是固定的，如果做ensumble需要提前打乱
        train_article_list = np.vstack([article_list[0:b], article_list[e:]])
        train_question_list = np.vstack([question_list[0:b], question_list[e:]])
        train_golden_span_list = np.vstack([golden_span_list[0:b], golden_span_list[e:]])
        train_word_match = np.vstack([word_match[0:b], word_match[e:]])

        print("total train_size:", len(train_article_list))
        train_dataset = RCData(train_article_list, train_question_list, train_golden_span_list, train_word_match)
        self.train_loader = DataLoader(dataset=train_dataset,
                                        batch_size=self.batch_size,
                                        shuffle=False)

        valid_dataset = RCValidData(article_list[b:e], question_list[b:e], word_match[b:e])
        print("total valid_size:", e-b)
        self.valid_loader = DataLoader(dataset=valid_dataset,
                                       batch_size=self.args.valid_batch_size,
                                       shuffle=False)
        print("data loader built successfully")

    def build_test_dataset(self):
        article_list, question_list = [], []
        word_match = []
        article_id_list, question_id_list = [], []
        raw_article_list = []
        # 就算长度为0，也加进来
        for _, d in enumerate(self.data):
            temp_article = list(d['article_content'])
            if len(temp_article) > self.max_article_len:
                temp_article = temp_article[:self.max_article_len]
            else:
                temp_article.extend(["<PAD>"] * max(0, self.max_article_len - len(temp_article)))
            temp_article = self.word2idx_for_list(temp_article)

            for qa in d['questions']:
                # 问题答案对
                article_list.append(temp_article)
                temp_question = list(qa['question'])
                if len(temp_question) > self.max_question_len:
                    temp_question = temp_question[:self.max_question_len]
                else:
                    temp_question.extend(["<PAD>"] * max(0, self.max_question_len - len(temp_question)))
                temp_question = self.word2idx_for_list(temp_question)

                question_list.append(temp_question)
                raw_article_list.append(list(d['article_content'])[:self.max_article_len])
                article_id_list.append(d["article_id"])
                question_id_list.append(qa["questions_id"])

                tmp_word_match = [1 if w in list(qa['question']) else 0 for w in list(d['article_content'])]
                if len(tmp_word_match) > self.max_article_len:
                    tmp_word_match = tmp_word_match[:self.max_article_len]
                else:
                    tmp_word_match.extend([0] * max(0, self.max_article_len - len(tmp_word_match)))
                word_match.append(tmp_word_match)

        article_list = np.array(article_list, dtype=np.int64)
        question_list = np.array(question_list, dtype=np.int64)
        word_match = np.array(word_match, dtype=np.int64)
        print(len(raw_article_list), len(article_id_list), len(question_id_list))

        train_size = len(question_list)
        print("total size:", train_size)

        self.test_raw_article_list = raw_article_list
        self.test_article_id_list = article_id_list
        self.test_question_id_list = question_id_list

        valid_dataset = RCTestData(
                                   article=article_list,
                                   question=question_list,
                                   word_match=word_match,
                                   )
        self.test_loader = DataLoader(dataset=valid_dataset,
                                      batch_size=self.batch_size,
                                      shuffle=False)
        print("data loader built successfully")
