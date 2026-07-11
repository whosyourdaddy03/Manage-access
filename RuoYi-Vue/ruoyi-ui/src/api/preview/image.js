import request from '@/utils/request'

// 根据id查询图片
export function queryPicture(id) {
  return request({
    url: '/visiualization/data/queryPicture',
    method: 'get',
    params: { id },
    responseType: 'blob'
  }).then((response) => {
    // 后端调用 sendError 时返回的是非图片类型（如 application/json），通过 blob.type 判断
    if (!response.type || response.type.indexOf('image/') === -1) {
      return Promise.reject(new Error('图片ID无对应数据'))
    }
    return response
  })
}
