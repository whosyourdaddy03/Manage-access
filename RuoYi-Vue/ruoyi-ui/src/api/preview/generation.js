import request from '@/utils/request'

// 实时模型生成
export function generationModel() {
  return request({
    url: '/visiualization/data/generationModel',
    method: 'get'
  })
}
