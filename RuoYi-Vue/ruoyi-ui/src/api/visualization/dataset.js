import request from '@/utils/request'

// 查询数据集列表
export function queryDatasetList() {
  return request({
    url: '/visiualization/data/queryDatasetList',
    method: 'get'
  })
}

// 分页查询图片列表
export function queryImageList(folder, pageNum, pageSize) {
  return request({
    url: '/visiualization/data/queryImageList',
    method: 'get',
    params: { folder, pageNum, pageSize }
  })
}

// 根据id查询带标注的图片(blob)
export function queryPicture(id) {
  return request({
    url: '/visiualization/data/queryPicture',
    method: 'get',
    params: { id },
    responseType: 'blob'
  }).then((response) => {
    if (!response.type || response.type.indexOf('image/') === -1) {
      return Promise.reject(new Error('图片ID无对应数据'))
    }
    return response
  })
}

// 查询标注原始数据
export function queryRawData(id) {
  return request({
    url: '/visiualization/data/queryRawData',
    method: 'get',
    params: { id }
  })
}

// 获取原始图片URL(可以直接在<img>中使用)
export function getRawImageUrl(id) {
  return process.env.VUE_APP_BASE_API + '/visiualization/data/getRawImage?id=' + id
}
