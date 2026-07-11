<template>
  <div class="app-container">
    <el-card>
      <div slot="header" class="card-header">
        <span><i class="el-icon-collection"></i> 数据集列表</span>
      </div>
      <el-table :data="datasetList" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="序号" type="index" width="60" align="center" />
        <el-table-column label="数据集名称" prop="name" min-width="180">
          <template slot-scope="scope">
            <span><i class="el-icon-folder-opened" style="color: #409eff; margin-right: 6px;"></i>{{ scope.row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="数据来源" prop="source" min-width="150" />
        <el-table-column label="图片总数" prop="totalCount" width="120" align="center" />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template slot-scope="scope">
            <el-button type="primary" size="mini" icon="el-icon-picture" @click="browseImages(scope.row)">
              浏览图片
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && datasetList.length === 0" description="暂无数据集数据" />
    </el-card>
  </div>
</template>

<script>
import { queryDatasetList } from '@/api/visualization/dataset'

export default {
  name: 'DataSetList',
  data() {
    return {
      loading: false,
      datasetList: []
    }
  },
  mounted() {
    this.fetchData()
  },
  methods: {
    fetchData() {
      this.loading = true
      queryDatasetList().then(response => {
        this.datasetList = response.data || []
      }).catch(() => {
        this.$modal.msgError('获取数据集列表失败')
      }).finally(() => {
        this.loading = false
      })
    },
    browseImages(row) {
      this.$router.push({ path: '/data-asset/image/' + row.folder })
    }
  }
}
</script>

<style scoped>
</style>
