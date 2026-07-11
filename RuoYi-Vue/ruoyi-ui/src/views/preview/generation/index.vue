<template>
  <div class="app-container">
    <el-card class="box-card">
      <div slot="header" class="card-header">
        <span><i class="el-icon-odometer"></i> 模型生成</span>
      </div>
      <div style="text-align: center; padding: 40px 0">
        <el-button type="primary" icon="el-icon-video-play" @click="handleGenerate" :loading="loading" size="large" style="font-size: 16px; padding: 15px 40px">
          开始生成模型
        </el-button>
        <div style="margin-top: 20px; color: #909399">
          <p v-if="!loading && !result">点击上方按钮开始实时模型生成</p>
          <p v-if="loading">模型生成中，请稍候...</p>
          <el-alert v-if="result" :title="result" type="success" show-icon center />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { generationModel } from "@/api/preview/generation"

export default {
  name: "ModelGeneration",
  data() {
    return {
      loading: false,
      result: ""
    }
  },
  methods: {
    handleGenerate() {
      this.loading = true
      this.result = ""
      generationModel().then((response) => {
        this.result = response.msg || "模型生成成功"
        this.$modal.msgSuccess(this.result)
      }).catch((err) => {
        this.$modal.msgError("模型生成失败：" + (err.message || "未知错误"))
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
