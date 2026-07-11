import request from '@/utils/request'

// 查询所有不同的epoch id组
export function queryAllEpochIds() {
  return request({
    url: '/visiualization/data/queryAllEpochIds',
    method: 'get'
  })
}

// 查询所有epoch结果
export function queryEpochResults() {
  return request({
    url: '/visiualization/data/queryEpochResults',
    method: 'get'
  })
}

// 按指定id分组查询epoch结果
export function queryEpochResultsByGroup(id) {
  return request({
    url: '/visiualization/data/queryEpochResultsByGroup',
    method: 'get',
    params: { id }
  })
}
