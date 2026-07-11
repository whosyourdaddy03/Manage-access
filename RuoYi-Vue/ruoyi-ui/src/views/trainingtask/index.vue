<template>
  <div class="app-container">
    <el-card>
      <div slot="header" class="card-header">
        <span><i class="el-icon-s-management"></i> 训练任务管理</span>
        <div style="float: right;">
          <el-button size="mini" icon="el-icon-refresh" @click="syncTasks" :loading="syncing">
            同步任务
          </el-button>
        </div>
      </div>

      <el-table :data="taskList" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="序号" type="index" width="60" align="center" />
        <el-table-column label="任务ID" prop="id" min-width="120" />
        <el-table-column label="训练时间" prop="trainingTime" min-width="170" />
        <el-table-column label="模型版本" prop="modelVersion" width="120" align="center" />
        <el-table-column label="Epochs" prop="epochs" width="100" align="center" />
        <el-table-column label="Batch Size" prop="batchSize" width="110" align="center" />
        <el-table-column label="Image Size" prop="imageSize" width="110" align="center" />
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template slot-scope="scope">
            <el-button type="primary" size="mini" icon="el-icon-s-data" @click="viewDetail(scope.row)">
              指标详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && taskList.length === 0" description="暂无训练任务数据，请点击同步任务" />
    </el-card>
  </div>
</template>

<script>
import { listTrainingTasks, syncTrainingTasks } from '@/api/visualization/training'

export default {
  name: 'TrainingTaskList',
  data() {
    return {
      loading: false,
      syncing: false,
      taskList: []
    }
  },
  mounted() {
    this.fetchData()
  },
  methods: {
    fetchData() {
      this.loading = true
      listTrainingTasks().then(response => {
        this.taskList = response.data || []
      }).catch(() => {
        this.$modal.msgError('获取训练任务列表失败')
      }).finally(() => {
        this.loading = false
      })
    },
    syncTasks() {
      this.syncing = true
      syncTrainingTasks().then(() => {
        this.$modal.msgSuccess('同步成功')
        this.fetchData()
      }).catch(() => {
        this.$modal.msgError('同步失败')
      }).finally(() => {
        this.syncing = false
      })
    },
    viewDetail(row) {
      this.$router.push({ path: '/training-task/detail/' + row.id })
    }
  }
}
</script>

<style scoped>
</style>
