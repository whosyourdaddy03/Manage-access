import request from '@/utils/request'

// 单张图片推理(返回JSON包含base64图片+检测信息)
export function singleInference(formData) {
  return request({
    url: '/visiualization/inference/single',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 启动批量推理
export function startBatchInference(formData) {
  return request({
    url: '/visiualization/inference/batch/start',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 查询批量任务状态
export function getBatchStatus(taskId) {
  return request({
    url: '/visiualization/inference/batch/status',
    method: 'get',
    params: { taskId }
  })
}

// 批量任务列表
export function listBatchTasks() {
  return request({
    url: '/visiualization/inference/batch/list',
    method: 'get'
  })
}

// 批量结果下载 URL
export function getBatchDownloadUrl(taskId) {
  return process.env.VUE_APP_BASE_API + '/visiualization/inference/batch/download?taskId=' + taskId
}

// 最新检测摘要
export function getLatestDetection() {
  return request({
    url: '/visiualization/inference/latest',
    method: 'get'
  })
}
