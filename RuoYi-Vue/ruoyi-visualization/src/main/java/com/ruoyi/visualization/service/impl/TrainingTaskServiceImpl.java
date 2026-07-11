package com.ruoyi.visualization.service.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.ruoyi.visualization.domain.TrainingTask;
import com.ruoyi.visualization.mapper.TrainingTaskMapper;
import com.ruoyi.visualization.service.TrainingTaskService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 训练任务 Service 实现
 */
@Service
public class TrainingTaskServiceImpl implements TrainingTaskService {

    private final Logger logger = LoggerFactory.getLogger(TrainingTaskServiceImpl.class);

    @Autowired
    private TrainingTaskMapper trainingTaskMapper;

    @Override
    public List<TrainingTask> selectTrainingTaskList() {
        return trainingTaskMapper.selectTrainingTaskList();
    }

    @Override
    public TrainingTask selectTrainingTaskById(String id) {
        return trainingTaskMapper.selectTrainingTaskById(id);
    }

    @Override
    public void syncTaskIds() {
        logger.info("同步训练任务ID开始");
        int count = trainingTaskMapper.syncTaskIds();
        logger.info("同步训练任务ID结束，新增 {} 条记录", count);
    }

    @Override
    public JSONArray selectEpochResultsByTaskId(String id) {
        List<Map<String, Object>> list = trainingTaskMapper.selectEpochResultsByTaskId(id);
        return (JSONArray) JSON.toJSON(list);
    }
}
