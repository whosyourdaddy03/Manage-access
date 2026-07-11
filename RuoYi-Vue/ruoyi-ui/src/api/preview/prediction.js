import request from '@/utils/request'

// 模型预测结果查询
export function queryPrediction() {
  return request({
    url: '/visiualization/data/queryPrediction',
    method: 'get'
  })
}
