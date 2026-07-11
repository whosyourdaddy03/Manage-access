import request from '@/utils/request'

// 查询已注册模型列表
export function listModels() {
  return request({
    url: '/visiualization/model/list',
    method: 'get'
  })
}

// 查询模型详情
export function getModelDetail(id) {
  return request({
    url: '/visiualization/model/detail',
    method: 'get',
    params: { id }
  })
}

// 注册模型
export function registerModel(data) {
  return request({
    url: '/visiualization/model/register',
    method: 'post',
    data
  })
}

// 更新模型
export function updateModel(data) {
  return request({
    url: '/visiualization/model/update',
    method: 'put',
    data
  })
}

// 删除模型
export function deleteModel(id) {
  return request({
    url: '/visiualization/model/delete',
    method: 'delete',
    params: { id }
  })
}

// 设为使用中
export function setModelInUse(id) {
  return request({
    url: '/visiualization/model/setInUse',
    method: 'post',
    params: { id }
  })
}

// 扫描本地模型文件
export function scanLocalModels(dirPath) {
  return request({
    url: '/visiualization/model/scanLocal',
    method: 'get',
    params: { dirPath }
  })
}
