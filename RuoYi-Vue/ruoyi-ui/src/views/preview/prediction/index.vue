<template>
  <div class="app-container">
    <el-card class="box-card">
      <div slot="header" class="card-header">
        <span><i class="el-icon-data-analysis"></i> 模型预测结果</span>
      </div>
      <el-button type="primary" icon="el-icon-search" @click="handleQuery" :loading="loading" style="margin-bottom: 15px">查询预测结果</el-button>

      <el-table v-loading="loading" :data="predictionList" border stripe style="width: 100%">
        <el-table-column label="序号" type="index" width="60" align="center" />
        <el-table-column label="ID" prop="id" min-width="120" align="center" />
        <el-table-column label="标签名称" prop="label" min-width="150" align="center" />
        <el-table-column label="置信度" prop="confidence" min-width="120" align="center">
          <template slot-scope="scope">
            <el-tag :type="scope.row.confidence > 0.8 ? 'success' : 'warning'">
              {{ (scope.row.confidence * 100).toFixed(2) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测时间" prop="createTime" min-width="180" align="center" />
      </el-table>

      <el-empty v-if="!loading && predictionList.length === 0" description="暂无预测数据，请点击查询" style="margin-top: 20px" />
    </el-card>
  </div>
</template>

<script>
import { queryPrediction } from "@/api/preview/prediction"

export default {
  name: "PredictionResult",
  data() {
    return {
      loading: false,
      predictionList: []
    }
  },
  methods: {
    handleQuery() {
      this.loading = true
      queryPrediction().then((response) => {
        this.predictionList = response.data || []
        this.$modal.msgSuccess("查询成功")
      }).catch((err) => {
        this.$modal.msgError("查询失败：" + (err.message || "未知错误"))
      }).finally(() => {
        this.loading = false
      })
    }
  }
}
</script>

<style scoped>
.card-header {
  font-size: 16px;
  font-weight: bold;
}
</style>
