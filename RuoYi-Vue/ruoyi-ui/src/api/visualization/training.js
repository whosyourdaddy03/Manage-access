import request from '@/utils/request'

// 查询训练任务列表
export function listTrainingTasks() {
  return request({
    url: '/visiualization/training/list',
    method: 'get'
  })
}

// 查询训练任务详情
export function getTrainingDetail(id) {
  return request({
    url: '/visiualization/training/detail',
    method: 'get',
    params: { id }
  })
}

// 同步训练任务ID
export function syncTrainingTasks() {
  return request({
    url: '/visiualization/training/sync',
    method: 'post'
  })
}

// 按任务ID查询epoch结果（图表数据，与首页使用同一数据源）
export function getEpochResultsByTask(id) {
  return request({
    url: '/visiualization/data/queryEpochResultsByGroup',
    method: 'get',
    params: { id }
  })
}

// 模型文件下载URL
export function getDownloadUrl(id, type) {
  return process.env.VUE_APP_BASE_API + '/visiualization/training/download?id=' + id + '&type=' + type
}
