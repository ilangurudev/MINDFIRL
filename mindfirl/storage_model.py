import os
import time
import hashlib
import config
import math
from get_pair_file import generate_pair_file, generate_fake_file
from blocking import generate_pair_by_blocking, update_result_to_intfile
import blocking
import numpy as np


class Assign_generator(object):
    def __init__(self, pair_file):
        with open(pair_file, 'r') as fin:
            self.lines = fin.readlines()

        self.idx = list(range(1, len(self.lines), 2))
        np.random.shuffle(self.idx)

        self.loc = 0
        self.size = len(self.idx)

        self.idx = self.idx + self.idx
            

    def random_assign(self, tmp_file, pair_num, block_id):
        selected = self.idx[self.loc:self.loc+pair_num]
        if self.loc + pair_num >= self.size:
            self.loc = pair_num - (self.size - self.loc)
        selected.sort()

        data = list()
        data.append(self.lines[0])
        assigned_id = list()
        for i in selected:
            data.append(self.lines[i])
            data.append(self.lines[i+1])
            cur_id = int(self.lines[i].split(',')[0])
            assigned_id.append(cur_id)

        with open(tmp_file, 'w+') as fout:
            for line in data:
                fout.write(line)

        # make assigned_id grouped in blocks
        grouped_assigned_id = list()
        for block in block_id:
            cur_block = list()
            for idx in assigned_id:
                if idx in block:
                    cur_block.append(idx)
            if cur_block:
                grouped_assigned_id.append(cur_block)

        return grouped_assigned_id

    def random_assign_pairfile(self, tmp_file, pair_num):
        selected = self.idx[self.loc:self.loc+pair_num]
        if self.loc + pair_num >= self.size:
            self.loc = pair_num - (self.size - self.loc)
        selected.sort()

        data = list()
        data.append(self.lines[0])
        assigned_id = list()
        for i in selected:
            data.append(self.lines[i])
            data.append(self.lines[i+1])
            cur_id = int(self.lines[i].split(',')[0])
            assigned_id.append(cur_id)

        with open(tmp_file, 'w+') as fout:
            for line in data:
                fout.write(line)

        # make assigned_id grouped in page of 6
        grouped_assigned_id = list()
        for i in range(0, len(assigned_id), 6):
            cur_block = assigned_id[i:i+6]
            grouped_assigned_id.append(cur_block)

        return grouped_assigned_id


def delete_file(path):
    try:
        os.remove(path)
    except Exception as e:
        print(e)


def get_total_pairs_from_pairfile(pairfile):
    cnt = 0
    with open(pairfile, 'r') as fin:
        for line in fin:
            if len(line) > 0:
                cnt += 1

    return (cnt-1)/2


def get_block_num(block_id, pf_file):
    """
    get how many blocks exist in the pf_file
    """
    pair_id = list()

    with open(pf_file, 'r') as fin:
        for line in fin:
            data = line.rstrip().split(',')
            pair_id.append(int(data[0]))

    pair_num = 0
    for cur_block in block_id:
        flag = False
        for value in cur_block:
            if value in pair_id:
                flag = True
                break
        if flag:
            pair_num += 1

    return pair_num


def save_project(mongo, data):
    project_name = data['project_name']
    project_des = data['project_des']
    owner = data['owner']

    pair_file = data['pair_file']
    file1 = data['file1']
    file2 = data['file2']

    file1_path = os.path.join(config.DATA_DIR, 'database', owner+'_'+project_name+'_file1.csv')
    file2_path = os.path.join(config.DATA_DIR, 'database', owner+'_'+project_name+'_file2.csv')
    pairfile_path = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_pairfile.csv')
    result_path = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_result.csv')

    # create result file
    f = open(result_path, 'w+')
    f.close()

    pair_file.save(pairfile_path)
    file1.save(file1_path)
    file2.save(file2_path)

    total_pairs = get_total_pairs_from_pairfile(pairfile_path)

    assigner = Assign_generator(pairfile_path)
    assignee_items = data['assignee_area'].rstrip(';').split(';')
    assignee_list = list()
    assignee_stat = list()
    for assignee_item in assignee_items:
        cur_assignee, cur_kapr, cur_percentage = assignee_item.split(',')
        assignee_list.append(cur_assignee)

        percentage = float(cur_percentage)/100.0
        tmp_file = os.path.join(config.DATA_DIR, 'internal', owner+'_'+cur_assignee+'_'+project_name+'_pairfile.csv')
        assigned_id = assigner.random_assign_pairfile(tmp_file=tmp_file, pair_num=int(total_pairs*percentage))
        pf_file = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_'+cur_assignee+'_pf.csv')
        pf_result = generate_pair_file(tmp_file, file1_path, file2_path, pf_file)
        delete_file(tmp_file)

        # create assignee result file
        cur_result = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_'+cur_assignee+'_result.csv')
        f = open(cur_result, 'w+')
        f.close()

        assignee_stat.append({
            'assignee': cur_assignee, 
            'pf_path': pf_file,
            'result_path': cur_result,
            'assigned_id': assigned_id,
            'current_page': 0, 
            'page_size': math.ceil(int(total_pairs*percentage)/6), 
            'pair_idx': 0,
            'total_pairs': math.ceil(int(total_pairs*percentage)),
            'kapr_limit': cur_kapr, 
            'current_kapr': 0
        })

    project_key = owner+'-'+project_name+str(time.time())
    project_key = project_key.encode('utf-8')
    pid = hashlib.sha224(project_key).hexdigest()

    project_data = {
        'pid': pid,
        'project_name': project_name, 
        'project_des': project_des, 
        'owner': owner,
        'created_by': 'pairfile',
        'file1_path': file1_path,
        'file2_path': file2_path,
        'pairfile_path': pairfile_path,
        'result_path': result_path,
        'assignee': assignee_list,
        'assignee_stat': assignee_stat
    }
    mongo.db.projects.insert(project_data)

    return pid


def save_project2(mongo, data):
    project_name = data['project_name']
    project_des = data['project_des']
    owner = data['owner']

    # generate pair_file for record linkage
    file1_path = os.path.join(config.DATA_DIR, 'database', owner+'_'+project_name+'_file1.csv')
    file2_path = os.path.join(config.DATA_DIR, 'database', owner+'_'+project_name+'_file2.csv')
    intfile_path = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_intfile.csv')
    pairfile_path = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_pairfile.csv')
    result_path = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_result.csv')
    file1 = data['file1']
    file2 = data['file2']
    file1.save(file1_path)
    file2.save(file2_path)

    total_pairs, block_id = generate_pair_by_blocking(blocking=data['blocking'], file1=file1_path, file2=file2_path, intfile=intfile_path, pair_file=pairfile_path)
    # if blocking_result is False, need to consider this

    # create result file
    f = open(result_path, 'w+')
    f.close()

    # assign the pairfile to each assignee, generate pf_file for them
    assigner = Assign_generator(pairfile_path)
    assignee_items = data['assignee_area'].rstrip(';').split(';')
    assignee_list = list()
    assignee_stat = list()
    for assignee_item in assignee_items:
        cur_assignee, cur_kapr, cur_percentage = assignee_item.split(',')
        assignee_list.append(cur_assignee)

        percentage = float(cur_percentage)/100.0
        tmp_file = os.path.join(config.DATA_DIR, 'internal', owner+'_'+cur_assignee+'_'+project_name+'_pairfile.csv')
        assigned_id = assigner.random_assign(tmp_file=tmp_file, pair_num=int(total_pairs*percentage), block_id=block_id)
        pf_file = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_'+cur_assignee+'_pf.csv')
        pf_result = generate_pair_file(tmp_file, file1_path, file2_path, pf_file)
        delete_file(tmp_file)

        total_blocks = get_block_num(block_id=block_id, pf_file=pf_file)

        # create assignee result file
        cur_result = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_'+cur_assignee+'_result.csv')
        f = open(cur_result, 'w+')
        f.close()

        assignee_stat.append({
            'assignee': cur_assignee, 
            'pf_path': pf_file,
            'result_path': cur_result,
            'assigned_id': assigned_id,
            'current_page': 0, 
            'page_size': total_blocks, 
            'kapr_limit': cur_kapr, 
            'current_kapr': 0,
            'pair_idx': 0,
            'total_pairs': pf_result['size'],
        })

    project_key = owner+'-'+project_name+str(time.time())
    project_key = project_key.encode('utf-8')
    pid = hashlib.sha224(project_key).hexdigest()

    project_data = {
        'pid': pid,
        'project_name': project_name, 
        'project_des': project_des, 
        'owner': owner,
        'created_by': 'blocking',
        'blocking_on': data['blocking'],
        'block_id': block_id,
        'file1_path': file1_path,
        'file2_path': file2_path,
        'intfile_path': intfile_path,
        'pairfile_path': pairfile_path,
        'result_path': result_path,
        'assignee': assignee_list,
        'assignee_stat': assignee_stat
    }
    mongo.db.projects.insert(project_data)

    return pid


def delete_project(mongo, pid, username):
    # delete related files
    project = mongo.db.projects.find_one({'pid': pid})
    file1_path = project['file1_path']
    file2_path = project['file2_path']
    if 'intfile_path' in project:
        intfile_path = project['intfile_path']
        delete_file(intfile_path)
    pairfile_path = project['pairfile_path']
    result_path = project['result_path']

    delete_file(file1_path)
    delete_file(file2_path)
    delete_file(pairfile_path)
    delete_file(result_path)

    assignee_stat = project['assignee_stat']
    for assignee in assignee_stat:
        pf_path = assignee['pf_path']
        result_path = assignee['result_path']
        delete_file(pf_path)
        delete_file(result_path)

    ret = mongo.db.projects.delete_one({'pid': pid})
    return ret


def get_projects_by_owner(mongo, owner):
    projects = mongo.db.projects.find({'owner': owner})
    return projects


def get_project_by_pid(mongo, pid):
    project = mongo.db.projects.find_one({'pid': pid})
    return project


def get_projects_assigned(mongo, user):
    assignments = mongo.db.projects.find({'assignee': user})
    return assignments


def get_assignment(mongo, username, pid):
    project = mongo.db.projects.find_one({'pid': pid})
    return project


def get_assignment_status(mongo, username, pid):
    """
    assignment status = 
    {
        'current_page': 1,
        'page_size': 6
    }
    """
    assignment = mongo.db.projects.find_one({'pid': pid})

    assignee_stat = assignment['assignee_stat']
    user_idx = 0
    while user_idx < len(assignee_stat) and assignee_stat[user_idx]['assignee'] != username:
        user_idx += 1
    if user_idx == len(assignee_stat):
        print("error: cannot find user as assignee in this project, pid: %s, username: %s" % (pid, username))
    current_page = assignee_stat[user_idx]['current_page']
    page_size = assignee_stat[user_idx]['page_size']
    kapr_limit = assignee_stat[user_idx]['kapr_limit']
    current_kapr = assignee_stat[user_idx]['current_kapr']

    ret = {
        'current_page': int(current_page),
        'page_size': int(page_size),
        'kapr_limit': float(kapr_limit),
        'current_kapr': float(current_kapr)
    }

    return ret


def get_assignee_result_path(mongo, pid, assignee):
    assignment = mongo.db.projects.find_one({'pid': pid})
    assignee_stat = assignment['assignee_stat']

    for item in assignee_stat:
        if item['assignee'] == assignee:
            return item['result_path']


def increase_assignment_page(mongo, username, pid):
    assignment = mongo.db.projects.find_one({'pid': pid})
    mongo.db.projects.update( {"pid": pid, "assignee_stat.assignee": username}, {"$inc": {"assignee_stat.$.current_page": 1}})


def increase_pair_idx(mongo, pid, username):
    assignment = mongo.db.projects.find_one({'pid': pid})

    pair_idx = 0
    assignee_stat = assignment['assignee_stat']
    for item in assignee_stat:
        if item['assignee'] == username:
            assignee = item
            break

    pair_idx = assignee['pair_idx']
    assigned_id = assignee['assigned_id']

    pos, i = 0, 0
    while pair_idx != pos and i < len(assigned_id):
        pos += len(assigned_id[i])
        i += 1
    inc = len(assigned_id[i])

    mongo.db.projects.update( {"pid": pid, "assignee_stat.assignee": username}, {"$inc": {"assignee_stat.$.pair_idx": inc}})


def update_kapr(mongo, username, pid, kapr):
    assignment = mongo.db.projects.find_one({'pid': pid})
    mongo.db.projects.update( {"pid": pid, "assignee_stat.assignee": username}, {"$set": {"assignee_stat.$.current_kapr": kapr}})


def get_data_mode(assignment_id, ids, r):
    mode_dict = {'M': 'masked', 'P': 'partial', 'F': 'full'}
    data_mode_list = []

    for (id1, id2) in ids:
        cur_list = []
        for attribute_id1 in id1:
            key = assignment_id + '-' + attribute_id1
            mode = r.get(key)
            if mode != None:
                cur_list.append(mode_dict[mode])
            else:
                r.set(key, 'M')
                cur_list.append('masked')
        data_mode_list.append(cur_list)

    return data_mode_list


def get_pair_datafile(mongo, user, pid):
    assignment = mongo.db.projects.find_one({'pid': pid})
    assignee_stat = assignment['assignee_stat']
    for item in assignee_stat:
        if item['assignee'] == user.username:
            return item['pf_path']


def get_all_users(mongo):
    users = mongo.db.users.find()
    return users


def save_working_answers(assignment_id, data, r):
    """
    save answered responses to redis
    data: string
    """
    answers = list()
    for d in data:
        if d['type'] == 'final_answer':
            answers.append(d['value'])

    working_answers = ','.join(answers)

    key = assignment_id + '-working_answers'
    r.delete(key)
    r.set(key, working_answers)

    return True


def get_working_answers(assignment_id, r):
    key = assignment_id + '-working_answers'
    answers = r.get(key)
    if not answers:
        return []
    return answers.split(',')


def clear_working_page_cache(assignment_id, r):
    for key in r.scan_iter(assignment_id+"*"):
        r.delete(key)


def save_answers(mongo, pid, username, data):
    """
    save one page answers to file
    """
    data_to_write = list()

    for d in data:
        if d['type'] == 'final_answer':
            answer = d['value']
            pair_num = int(answer.split('a')[0][1:])
            choice = int(answer.split('a')[1])
            decision = 1 if choice > 3 else 0
            line = ','.join([str(pair_num), str(decision), str(choice)])
            data_to_write.append(line)

    filename = get_assignee_result_path(mongo=mongo, pid=pid, assignee=username)

    with open(filename, 'a') as f:
        for item in data_to_write:
            f.write(item + '\n')

    return True


def save_resolve_conflicts(mongo, pid, username, data):
    """
    update the result file
    """
    final_answer = dict()
    for d in data:
        if d['type'] == 'final_answer':
            answer = d['value']
            pair_num = int(answer.split('a')[0][1:])
            choice = int(answer.split('a')[1])
            decision = 1 if choice > 3 else 0
            final_answer[pair_num] = ','.join([str(pair_num), str(decision), str(choice)])

    project = mongo.db.projects.find_one({'pid': pid})
    result_file = project['result_path']

    results = dict()
    with open(result_file, 'r') as fin:
        for line in fin:
            if line.strip() == '':
                continue
            pair_id, decision, choice = line.strip().split(',')
            if int(pair_id) in final_answer:
                results[int(pair_id)] = final_answer[int(pair_id)]
            else:
                results[int(pair_id)] = line.strip()

    with open(result_file, 'w+') as fout:
        for pair_id in sorted(results):
            fout.write(results[pair_id]+'\n')

    return True


def is_project_completed(mongo, pid):
    project = mongo.db.projects.find_one({'pid': pid})

    assignee_stat = project['assignee_stat']
    for assignee in assignee_stat:
        if int(assignee['current_page']) < int(assignee['page_size']):
            return False
    return True


def update_project_setting(mongo, user, data):
    pid = data['pid']
    project_name = data['project_name']
    project_des = data['project_des']
    #assignee = data['assignee']
    #kapr_limit = data['kapr_limit']

    mongo.db.projects.update({"pid": pid}, {"$set": {"project_name": project_name, "project_des": project_des}})

    #mongo.db.projects.update( {"pid": pid, "assignee_stat.assignee": assignee}, {"$set": {"assignee_stat.$.kapr_limit": float(kapr_limit)}})

    return True


def project_name_existed(mongo, data):
    project_name = data['project_name']
    owner = data['owner']
    existed = mongo.db.projects.find_one({'owner': owner, 'project_name': project_name})
    if existed:
        return True
    return False


def is_invalid_kapr(mongo, data):
    project = mongo.db.projects.find_one({'pid': data['pid']})

    assignee_stat = project['assignee_stat']
    user_idx = 0
    current_kapr = assignee_stat[user_idx]['current_kapr']

    if 100*float(current_kapr) > float(data['kapr_limit']):
        return True
    return False


def get_current_kapr(mongo, data):
    project = mongo.db.projects.find_one({'pid': data['pid']})

    assignee_stat = project['assignee_stat']
    user_idx = 0
    current_kapr = assignee_stat[user_idx]['current_kapr']

    current_kapr = round(100*float(current_kapr), 2)

    return current_kapr


def get_current_block(mongo, pid, assignee):
    """
    get pair id for current block (one block per page)
    """
    assignment = mongo.db.projects.find_one({'pid': pid})
    assignee_stat = assignment['assignee_stat']

    for item in assignee_stat:
        if item['assignee'] == assignee:
            cur_assignee = item
            break

    pair_idx = cur_assignee['pair_idx']
    assigned_id = cur_assignee['assigned_id']

    pos = 0
    i = 0
    while pair_idx != pos and i < len(assigned_id):
        pos += len(assigned_id[i])
        i += 1

    ret = assigned_id[i]

    return ret, pair_idx


def combine_result(mongo, pid):
    project = mongo.db.projects.find_one({'pid': pid})

    result_file = project['result_path']
    pairfile_path = project['pairfile_path']

    results = list()
    assignee_stat = project['assignee_stat']
    for assignee in assignee_stat:
        cur_result = assignee['result_path']
        with open(cur_result, 'r') as fin:
            for line in fin:
                if line:
                    results.append(line)
        # reset this result file
        with open(cur_result, 'w+') as fout:
            fout.write('')

    with open(result_file, 'a') as fout:
        for item in results:
            fout.write(item)

    return True


def update_result(mongo, pid):
    project = mongo.db.projects.find_one({'pid': pid})

    if project['created_by'] == 'pairfile':
        return True

    result_file = project['result_path']
    pairfile_path = project['pairfile_path']
    intfile_path = project['intfile_path']

    update_result_to_intfile(result_file, pairfile_path, intfile_path)

    # reset result file
    fout = open(result_file, 'w+')
    fout.close()

    return True


def get_result_path(mongo, pid):
    project = mongo.db.projects.find_one({'pid': pid})
    if project['created_by'] == 'pairfile':
        return project['result_path']
    else:
        return project['intfile_path']


def detect_result_conflicts(mongo, pid):
    project = mongo.db.projects.find_one({'pid': pid})

    result_file = project['result_path']

    pair_id = dict()
    conflicts = list()
    with open(result_file, 'r') as fin:
        for line in fin:
            if line.strip() == '':
                continue
            data = line.split(',')
            cur_id = int(data[0])
            if cur_id in pair_id:
                conflicts.append(cur_id)
            else:
                pair_id[cur_id] = 1

    return conflicts


def new_blocking(mongo, data):
    project = mongo.db.projects.find_one({'pid': data['pid']})
    pid=data['pid']
    project_name = project['project_name']
    owner = project['owner']
    assignee = project['assignee'][0]
    file1_path = project['file1_path']
    file2_path = project['file2_path']
    intfile_path = project['intfile_path']
    pairfile_path = project['pairfile_path']

    total_pairs, block_id = blocking.new_blocking(blocking=data['blocking'], intfile=intfile_path, pair_file=pairfile_path)

    assignee_items = data['assignee_area'].rstrip(';').split(';')
    assignee_list = list()
    assignee_stat = list()
    for assignee_item in assignee_items:
        cur_assignee, cur_kapr, cur_percentage = assignee_item.split(',')
        assignee_list.append(cur_assignee)

        percentage = float(cur_percentage)/100.0
        tmp_file = os.path.join(config.DATA_DIR, 'internal', owner+'_'+cur_assignee+'_'+project_name+'_pairfile.csv')
        assigned_id = random_assign(pair_file=pairfile_path, tmp_file=tmp_file, pair_num=int(total_pairs*percentage), block_id=block_id)
        pf_file = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_'+cur_assignee+'_pf.csv')
        pf_result = generate_pair_file(tmp_file, file1_path, file2_path, pf_file)
        delete_file(tmp_file)

        total_blocks = get_block_num(block_id=block_id, pf_file=pf_file)

        # create result file
        cur_result = os.path.join(config.DATA_DIR, 'internal', owner+'_'+project_name+'_'+cur_assignee+'_result.csv')
        f = open(cur_result, 'w+')
        f.close()

        assignee_stat.append({
            'assignee': cur_assignee, 
            'pf_path': pf_file,
            'result_path': cur_result,
            'assigned_id': assigned_id,
            'current_page': 0, 
            'page_size': total_blocks, 
            'kapr_limit': cur_kapr, 
            'current_kapr': 0,
            'pair_idx': 0,
            'total_pairs': pf_result['size'],
        })

    mongo.db.projects.update( {"pid": pid}, {"$set": {"assignee": assignee_list}})
    mongo.db.projects.update( {"pid": pid}, {"$set": {"assignee_stat": assignee_stat}})

    return pid


def mlog(mongo, data):
    mongo.db.log.insert(data)



